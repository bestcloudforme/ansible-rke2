# ansible-rke2

Production-ready Ansible playbooks for deploying RKE2 Kubernetes clusters. Supports single-master dev setups and full HA production clusters with HAProxy + keepalived.

## Features

- **Full Lifecycle**: install, upgrade, add/remove nodes, uninstall, etcd backup/restore, cert rotation
- **HA Support**: 3-master clusters with HAProxy + keepalived VIP, or kube-vip, or external LB
- **CIS Hardening**: Optional `profile: cis` startup validation against the CIS Kubernetes Benchmark
- **Multi-OS**: RHEL/Rocky/AlmaLinux 9 and Ubuntu 22.04/24.04 (Debian 12 best effort)
- **CNI Choice**: Canal, Calico, or Cilium (with kube-proxy replacement and BPF masquerade)
- **Airgap**: Online and offline installation support
- **EKS Distro**: Private registry mirror for EKS-D images
- **Custom Manifests**: Auto-deploy custom Kubernetes manifests on server start
- **Production Hardening**: etcd snapshots, audit logging, Pod Security Admission, resource reservations, kernel hardening, system limits, log rotation
- **Multi-Environment**: Shared roles, per-cluster environment configs
- **Rolling Upgrades**: Masters serial:1, workers serial:25% with drain/uncordon

## Compatibility Matrix

| Component | Supported |
|-----------|-----------|
| **ansible-core** | 2.19 - 2.21 |
| **Python (control node)** | 3.11 - 3.13 |
| **Python (managed node)** | 3.9+ |
| **RKE2** | v1.33.x - v1.36.x |
| **RHEL / Rocky / AlmaLinux** | 9.x |
| **Ubuntu** | 22.04, 24.04 |
| **Debian** | 12 (best effort) |
| **kube-vip** | v1.2.3 |

`rke2_version` has no default and must be set. The RKE2 stable channel is at
**v1.35.7+rke2r1** as of 2026-08-21; check
[update.rke2.io](https://update.rke2.io/v1-release/channels) for the current one.

**Validated on:** Rocky Linux 9.8 and Ubuntu 24.04 LTS, 3-master HA with HAProxy
and keepalived, RKE2 v1.35.7 and v1.36.3, Canal and Calico. The `kube-vip` and
airgap paths are implemented to spec but not covered by that testing - see
[docs/testing.md](docs/testing.md).

**Required collections:**

| Collection | Version |
|-----------|---------|
| `ansible.posix` | >= 2.2.0, < 3.0.0 |
| `community.general` | >= 13.0.0, < 14.0.0 |

## Quick Start

```bash
# Install dependencies
ansible-galaxy collection install -r requirements.yml

# Edit your inventory
cp -r environments/example environments/my-cluster
vi environments/my-cluster/inventory/hosts.yml
vi environments/my-cluster/inventory/group_vars/all.yml

# Deploy
ansible-playbook playbooks/install.yml \
  -i environments/my-cluster/inventory/hosts.yml
```

## Directory Structure

```
ansible-rke2/
├── docs/                               # Operational runbooks and guides
│   ├── testing.md                      # What is tested on real hosts, and what is not
│   ├── upgrade-checklist.md
│   ├── backup-restore-runbook.md
│   └── vault-guide.md
├── environments/
│   ├── example/                        # Single-master example
│   │   ├── inventory/
│   │   │   ├── hosts.yml
│   │   │   └── group_vars/
│   │   └── cluster.yml                 # Cluster metadata (name, env, notes)
│   └── ha-example/                     # HA cluster example (3 master + 2 HAProxy)
│       ├── inventory/
│       │   ├── hosts.yml
│       │   └── group_vars/
│       │       ├── all.yml             # Cluster-wide vars
│       │       ├── masters.yml         # Master-specific vars
│       │       ├── workers.yml         # Worker-specific vars
│       │       └── loadbalancers.yml   # HAProxy/keepalived vars
│       └── cluster.yml
├── meta/runtime.yml                    # Minimum ansible-core for the collection
├── playbooks/
│   ├── install.yml                     # Fresh cluster install
│   ├── upgrade.yml                     # Rolling upgrade
│   ├── add_node.yml                    # Add worker or master
│   ├── remove_node.yml                 # Remove node from cluster
│   ├── uninstall.yml                   # Full teardown
│   ├── etcd_backup.yml                 # etcd snapshot backup (local + S3)
│   ├── etcd_restore.yml                # etcd snapshot restore
│   ├── rotate_certs.yml                # TLS certificate rotation
│   └── fetch_kubeconfig.yml            # Download kubeconfig to controller
├── roles/
│   ├── rke2_common/                    # Shared defaults; dependency of every other role
│   ├── preflight/                      # OS prerequisites (modules, sysctl, packages, firewall)
│   ├── rke2_server/                    # Master node installation and config
│   ├── rke2_agent/                     # Worker node installation and config
│   ├── cni/                            # CNI readiness check (canal/calico/cilium/none)
│   ├── lb/                             # kube-vip or external LB setup
│   ├── haproxy/                        # HAProxy + keepalived for HA
│   ├── eksd_images/                    # EKS Distro image configuration
│   └── lifecycle/                      # Upgrade, node removal, uninstall, backup, cert rotation
└── tests/
    └── vars-precedence.yml             # Guards the group_vars override path; runs in CI
```

## Network Requirements

All RKE2 nodes require the following ports open between them:

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 6443 | TCP | Inbound | Kubernetes API server |
| 9345 | TCP | Inbound | RKE2 supervisor API (node join) |
| 2379 | TCP | Masters only | etcd client |
| 2380 | TCP | Masters only | etcd peer |
| 8472 | UDP | All nodes | VXLAN overlay (Canal/Flannel) |
| 10250 | TCP | All nodes | kubelet metrics |
| 179 | TCP | All nodes | BGP (Calico only) |
| 4240 | TCP | All nodes | Cilium health check (Cilium only) |
| 8090 | TCP | All nodes | Cilium Hubble (Cilium only) |

**HAProxy nodes (when `rke2_lb_type: haproxy`):**

| Port | Protocol | Purpose |
|------|----------|---------|
| 6443 | TCP | API frontend (proxied to masters) |
| 9345 | TCP | Join frontend (proxied to masters) |
| 9000 | TCP | HAProxy stats page — binds to `127.0.0.1` by default, so no inbound rule is needed unless you change `haproxy_stats_bind` |

**Firewall handling:**

- **RHEL/Rocky/Alma**: with the default `preflight_firewalld_mode: configure`, the
  `preflight` role opens the ports above and adds `rke2_cluster_cidr` and
  `rke2_service_cidr` to the `trusted` zone — pod traffic is not port-scoped, so
  without that cross-node pod networking is dropped. Only applied when firewalld
  is actually running. Set the mode to `disable` (what RKE2 documents) or
  `ignore` to opt out.
- **Ubuntu/Debian**: the same ports and CIDRs via `ufw`, whenever ufw is
  installed. Rules are recorded even while ufw is inactive, which is what stops
  a later `ufw enable` locking the cluster out.
- Ports are selected per node role and per CNI, so masters additionally get etcd
  2379/2380/2381 and the CNI's own ports.
- Load balancer nodes are handled by the `haproxy` role, not `preflight`.
- If you use a different firewall, open the ports listed above manually.

## Playbooks

### Install

```bash
ansible-playbook playbooks/install.yml \
  -i environments/my-cluster/inventory/hosts.yml
```

Execution order:
1. Validate the inventory — `rke2_version`, exactly one `rke2_bootstrap` master
   and it must be first in the group, `rke2_master_count`, no host in both
   `masters` and `workers`
2. Gather facts from masters, workers and load balancers — the HAProxy backend
   list is built from them
3. Phase 0: HAProxy + keepalived (if `rke2_lb_type: haproxy`)
4. Phase 1: OS prerequisites on masters and workers
5. Phase 2: kube-vip manifest (if `rke2_master_count > 1` and not `haproxy`)
6. Phase 3: masters, `serial: 1` — also renders the audit policy and PSA config
7. Phase 4: EKS-D images (optional)
8. Phase 5: workers
9. Phase 6: CNI readiness check

### Upgrade

```bash
ansible-playbook playbooks/upgrade.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_version=v1.36.3+rke2r1"
```

Rolling upgrade with cordon/drain/uncordon. Masters upgraded one at a time, workers at 25%. If an upgrade fails mid-flight, the node is automatically uncordoned.

**Note:** Drain, cordon and readiness checks look the node up by `rke2_node_name`,
which defaults to the node's full hostname (`ansible_nodename`) lowercased - the
name RKE2 registers. Set `rke2_node_name` if you override `node-name` in the RKE2
config.

**Pre-upgrade checklist:** See [docs/upgrade-checklist.md](docs/upgrade-checklist.md)

### Add Node

```bash
# Add worker (add to inventory first)
ansible-playbook playbooks/add_node.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "target_hosts=new_worker"

# Add master
ansible-playbook playbooks/add_node.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "target_hosts=new_master node_role=master"
```

### Remove Node

```bash
ansible-playbook playbooks/remove_node.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "node_name=worker-3"

# Removing a master: pass node_role so the HAProxy backends are re-rendered.
# The play refuses to drop the control plane below three nodes unless you also
# pass rke2_allow_quorum_loss=true.
ansible-playbook playbooks/remove_node.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "node_name=master-3 node_role=master"

# If Kubernetes node name differs from Ansible inventory hostname:
ansible-playbook playbooks/remove_node.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "node_name=worker-3 target_host=worker-3.example.com"
```

### etcd Backup

```bash
# Local snapshot
ansible-playbook playbooks/etcd_backup.yml \
  -i environments/my-cluster/inventory/hosts.yml

# Named snapshot
ansible-playbook playbooks/etcd_backup.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_etcd_backup_name=pre-upgrade-v1.36"
```

S3 backup is supported — configure `rke2_etcd_s3_*` variables in `group_vars/all.yml`.

**Full backup/restore guide:** See [docs/backup-restore-runbook.md](docs/backup-restore-runbook.md)

### etcd Restore

```bash
# Restore from local snapshot
ansible-playbook playbooks/etcd_restore.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_etcd_restore_snapshot=/var/lib/rancher/rke2/server/db/snapshots/my-snapshot"

# Restore from S3
ansible-playbook playbooks/etcd_restore.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_etcd_restore_snapshot=my-snapshot-name"
```

**Warning:** This stops all masters, restores etcd on the bootstrap master, and rejoins other masters.

### Certificate Rotation

```bash
ansible-playbook playbooks/rotate_certs.yml \
  -i environments/my-cluster/inventory/hosts.yml
```

Rotates TLS certificates on masters (serial: 1) then restarts workers to pick up new certs.

### Fetch Kubeconfig

```bash
ansible-playbook playbooks/fetch_kubeconfig.yml \
  -i environments/my-cluster/inventory/hosts.yml

# Custom output path
ansible-playbook playbooks/fetch_kubeconfig.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "kubeconfig_local_path=~/.kube/my-cluster.yaml"
```

Downloads kubeconfig from the bootstrap master with the server URL rewritten to the LB address.

### Uninstall

```bash
ansible-playbook playbooks/uninstall.yml \
  -i environments/my-cluster/inventory/hosts.yml
```

## Configuration

### Topology Examples

**Single master (dev/test):**
```yaml
# group_vars/all.yml
rke2_master_count: 1
rke2_lb_type: "external"
rke2_lb_external_host: "192.168.1.10"
```

**HA with HAProxy (production):**
```yaml
# group_vars/all.yml
rke2_master_count: 3
rke2_lb_type: "haproxy"
rke2_lb_vip: "192.168.1.100"
# rke2_vip_interface: ""   # empty autodetects the default-route interface
```

**HA with kube-vip:**
```yaml
# group_vars/all.yml
rke2_master_count: 3
rke2_lb_type: "kube-vip"
rke2_lb_vip: "192.168.1.100"
# rke2_vip_interface: ""   # empty autodetects the default-route interface
```

### Production Hardening

```yaml
# group_vars/all.yml
rke2_etcd_snapshot_schedule: "0 */6 * * *"   # Every 6 hours
rke2_etcd_snapshot_retention: 10
rke2_audit_policy_enabled: true
rke2_pod_security_admission: "restricted"
rke2_kube_reserved_cpu: "500m"
rke2_kube_reserved_memory: "512Mi"
rke2_system_reserved_cpu: "500m"
rke2_system_reserved_memory: "512Mi"
rke2_protect_kernel_defaults: true
```

### Group Vars Structure

For HA clusters, split variables across group-specific files:

```
group_vars/
├── all.yml              # Cluster-wide: version, CNI, LB config, hardening
├── masters.yml          # Master-specific: taints, labels
├── workers.yml          # Worker-specific: labels
└── loadbalancers.yml    # HAProxy/keepalived: passwords, VIP interface
```

See `environments/ha-example/` for a complete example.

### Variables Reference

All defaults live in `roles/rke2_common/defaults/main.yml` and the individual
roles' `defaults/main.yml`. Every role depends on `rke2_common`, so overriding a
variable in `group_vars/` takes effect everywhere.

#### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_version` | `""` | RKE2 version. **Required** — there is no default |
| `rke2_channel` | `stable` | Release channel, consulted only when no explicit version is given |
| `rke2_cni` | `canal` | CNI plugin: `canal`, `calico`, `cilium` or `none` |
| `rke2_master_count` | `1` | Number of masters. Must match the `masters` group size |
| `rke2_bootstrap` | `false` | **Per-host.** `true` on exactly one master, which must be first in the `masters` group |
| `rke2_cluster_cidr` | `10.42.0.0/16` | Pod network CIDR |
| `rke2_service_cidr` | `10.43.0.0/16` | Service network CIDR |
| `rke2_cilium_kube_proxy_replacement` | `true` | Replace kube-proxy with Cilium eBPF (`cni=cilium`) |
| `rke2_cilium_bpf_masquerade` | `true` | BPF masquerading instead of iptables (`cni=cilium`) |
| `rke2_custom_manifests` | `[]` | Local manifest paths auto-deployed on server start |

#### Node identity

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_node_name` | derived | Kubernetes node name used for cordon, drain and readiness lookups |
| `rke2_node_ip` | `""` | `node-ip` to advertise, for multi-NIC hosts |
| `rke2_node_external_ip` | `""` | `node-external-ip` to advertise |
| `rke2_selinux` | `false` | Enable SELinux support in containerd (RHEL family) |

#### Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_data_dir` | `/var/lib/rancher/rke2` | RKE2 data directory |
| `rke2_config_dir` | `/etc/rancher/rke2` | RKE2 config directory |
| `rke2_bin_dir` | derived | Runtime bundle (`kubectl`, `crictl`, `ctr`) — not the `rke2` CLI |
| `rke2_install_bin_dir` | derived | Where `get.rke2.io` puts the CLI: rpm on RHEL-family, tarball elsewhere |
| `rke2_cli` | derived | Path to the `rke2` CLI |
| `rke2_killall_script` | derived | Path to `rke2-killall.sh` |
| `rke2_uninstall_script` | derived | Path to `rke2-uninstall.sh` |
| `rke2_install_script` | `/root/.rke2-install.sh` | Where the install script is written — deliberately not world-writable `/tmp` |
| `rke2_kubeconfig_mode` | `0640` | Mode for `/etc/rancher/rke2/rke2.yaml` |
| `rke2_server_token` | `""` | Cluster join token. Read from the bootstrap master automatically |

#### Load balancer

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_lb_type` | `external` | LB type: `kube-vip`, `external` or `haproxy` |
| `rke2_lb_vip` | `""` | Virtual IP (required for `kube-vip`/`haproxy`) |
| `rke2_lb_external_host` | `""` | External LB host (required for `external`) |
| `rke2_vip_interface` | `""` | Interface for the VIP. Empty autodetects the default-route interface |
| `rke2_server_tls_san` | `[]` | Additional TLS SANs for the API server certificate |
| `rke2_kube_vip_version` | `v1.2.3` | kube-vip image tag |

#### HAProxy

| Variable | Default | Description |
|----------|---------|-------------|
| `haproxy_api_frontend_port` | `6443` | Kubernetes API frontend port |
| `haproxy_join_frontend_port` | `9345` | RKE2 supervisor frontend port |
| `haproxy_balance_algorithm` | `roundrobin` | Backend balance algorithm |
| `haproxy_maxconn` | `3000` | Maximum connections |
| `haproxy_retries` | `2` | Connection retries before redispatch |
| `haproxy_timeout_client` | `4h` | Client timeout — long enough for `kubectl exec` and `logs -f` |
| `haproxy_timeout_server` | `4h` | Server timeout |
| `haproxy_timeout_tunnel` | `4h` | Tunnel timeout for upgraded connections |
| `haproxy_check_interval` | `3s` | Backend health check interval |
| `haproxy_check_fall` | `3` | Failed checks before a backend is marked down |
| `haproxy_check_rise` | `2` | Successful checks before a backend is marked up |
| `haproxy_stats_bind` | `127.0.0.1` | Address the stats page binds to |
| `haproxy_stats_port` | `9000` | Stats page port |
| `haproxy_stats_user` | `admin` | Stats page user |
| `haproxy_stats_password` | `changeme` | Stats page password. **Must be changed** — the role asserts it |

#### Keepalived

| Variable | Default | Description |
|----------|---------|-------------|
| `keepalived_vrrp_interface` | derived | VRRP interface. Follows `rke2_vip_interface`, else the default route |
| `keepalived_vrrp_id` | `51` | VRRP router ID. Must be unique on the L2 segment |
| `keepalived_priority` | derived | VRRP priority, descending by inventory position |
| `keepalived_unicast_src_ip` | derived | Source address for VRRP adverts |
| `keepalived_auth_pass` | `rke2ha` | VRRP auth password, max 8 chars. **Must be changed** — the role asserts it |
| `keepalived_check_script_path` | `/usr/local/bin/check_apiserver.sh` | Path to the health check script |
| `keepalived_check_interval` | `3` | Health check interval in seconds |
| `keepalived_check_fall` | `3` | Failed checks before FAULT |
| `keepalived_check_rise` | `2` | Successful checks before recovery |

#### CNI verification

| Variable | Default | Description |
|----------|---------|-------------|
| `cni_pod_selector` | see role defaults | Pod label selector per CNI, used by the readiness check |
| `cni_wait_retries` | `40` | Readiness retries. Calico goes through an operator and is slow on first boot |
| `cni_wait_delay` | `15` | Seconds between readiness checks |

#### Lifecycle

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_drain_timeout` | `300s` | Node drain timeout |
| `rke2_drain_force` | `true` | Pass `--force` to drain, so a bare pod does not stall it |
| `rke2_upgrade_serial` | `1` | Masters upgraded per batch |
| `rke2_upgrade_agent_serial` | `25%` | Workers upgraded per batch |
| `rke2_api_ready_timeout` | `600` | Seconds to wait for the apiserver after a restart |
| `rke2_service_start_retries` | `30` | Retries while waiting for a service to become active |
| `rke2_reboot_after_uninstall` | `false` | Reboot nodes after uninstall |

#### Hardening

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_cis_profile` | `""` | Startup benchmark validation: `cis` or `etcd`. Implies `protect-kernel-defaults` |
| `rke2_protect_kernel_defaults` | `false` | Make kubelet validate kernel parameters instead of setting them |
| `rke2_pod_security_admission` | `""` | PSA level: `restricted`, `baseline` or `privileged` |
| `rke2_pod_security_exemptions` | see role defaults | Namespaces exempt from PSA enforcement |
| `rke2_audit_policy_enabled` | `false` | Enable API server audit logging |
| `rke2_audit_log_dir` | derived | Audit log directory — RKE2 mounts this one into the apiserver pod |
| `rke2_audit_log_maxage` | `30` | Audit log max age in days |
| `rke2_audit_log_maxbackup` | `10` | Audit log files retained |
| `rke2_audit_log_maxsize` | `100` | Audit log max size in MB |
| `rke2_kube_reserved_cpu` | `""` | CPU reserved for kubelet |
| `rke2_kube_reserved_memory` | `""` | Memory reserved for kubelet |
| `rke2_system_reserved_cpu` | `""` | CPU reserved for the system |
| `rke2_system_reserved_memory` | `""` | Memory reserved for the system |
| `rke2_eviction_hard` | `""` | kubelet hard eviction thresholds |
| `rke2_server_node_taints` | `[]` | Taints for master nodes |
| `rke2_server_node_labels` | `[]` | Labels for masters. `node-role.kubernetes.io/*` is rejected by NodeRestriction |
| `rke2_agent_node_labels` | `[]` | Labels for workers. Same restriction applies |
| `rke2_agent_node_taints` | `[]` | Taints for worker nodes |

#### etcd snapshots

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_etcd_snapshot_schedule` | `""` | Cron schedule for etcd snapshots |
| `rke2_etcd_snapshot_retention` | `5` | Snapshots retained |
| `rke2_etcd_snapshot_dir` | derived | Local snapshot directory |
| `rke2_etcd_s3_enabled` | `false` | Send etcd snapshots to S3 |
| `rke2_etcd_s3_endpoint` | `""` | S3 endpoint |
| `rke2_etcd_s3_bucket` | `""` | S3 bucket |
| `rke2_etcd_s3_region` | `""` | S3 region |
| `rke2_etcd_s3_access_key` | `""` | S3 access key — use vault |
| `rke2_etcd_s3_secret_key` | `""` | S3 secret key — use vault |
| `rke2_etcd_s3_folder` | `""` | S3 prefix |
| `rke2_etcd_s3_skip_ssl_verify` | `false` | Skip S3 TLS verification |

#### Airgap and registry

| Variable | Default | Description |
|----------|---------|-------------|
| `rke2_airgap` | `false` | Enable airgap installation |
| `rke2_airgap_images_path` | `/opt/rke2-artifacts` | Directory on the node holding the artifacts |
| `rke2_airgap_local_artifacts` | `""` | Controller-side artifacts for `rke2_version`. Required for an airgap **upgrade** |
| `rke2_registry_mirror` | `""` | Private registry mirror |
| `rke2_registry_mirror_tls_skip` | `false` | Skip TLS verification for the mirror |

#### EKS Distro

| Variable | Default | Description |
|----------|---------|-------------|
| `eksd_enabled` | `false` | Enable EKS-D image configuration |
| `eksd_registry` | `public.ecr.aws/eks-distro` | EKS-D registry |

#### Preflight

| Variable | Default | Description |
|----------|---------|-------------|
| `preflight_selinux_state` | `""` | `enforcing`, `permissive`, or empty to leave SELinux alone |
| `preflight_firewalld_mode` | `configure` | `configure`, `disable` or `ignore` |
| `preflight_firewall_ports` | see role defaults | Base ports opened on every node |
| `preflight_firewall_ports_master` | see role defaults | Extra ports opened on masters (etcd) |
| `preflight_firewall_ports_cni` | see role defaults | Extra ports per CNI |
| `preflight_required_kernel_modules` | see role defaults | Modules loaded and persisted |
| `preflight_load_ipvs_modules` | `false` | Also load `ip_vs*`. RKE2 kube-proxy runs in iptables mode |
| `preflight_ipvs_kernel_modules` | see role defaults | The IPVS module list |
| `preflight_sysctl_params` | see role defaults | sysctl values applied on every node |
| `preflight_kernel_defaults_sysctl` | see role defaults | Parameters kubelet validates under `protect-kernel-defaults` |
| `preflight_nofile_limit` | `1024000` | `nofile` limit |
| `preflight_nproc_limit` | `1024000` | `nproc` limit |
| `preflight_logrotate_maxsize` | `250M` | Container log rotation size |

## Airgap Installation

For airgap (offline) environments:

1. **Download artifacts** on an internet-connected machine:
   ```bash
   # Download RKE2 artifacts for your target version
   RKE2_VERSION="v1.35.7+rke2r1"
   mkdir -p rke2-artifacts && cd rke2-artifacts
   curl -LO "https://github.com/rancher/rke2/releases/download/${RKE2_VERSION}/rke2-images.linux-amd64.tar.zst"
   curl -LO "https://github.com/rancher/rke2/releases/download/${RKE2_VERSION}/rke2.linux-amd64.tar.gz"
   curl -LO "https://github.com/rancher/rke2/releases/download/${RKE2_VERSION}/sha256sum-amd64.txt"
   curl -sfL https://get.rke2.io -o install.sh && chmod +x install.sh
   ```

2. **Transfer artifacts** to all target nodes at `rke2_airgap_images_path` (default: `/opt/rke2-artifacts/`).

3. **Configure inventory:**
   ```yaml
   # group_vars/all.yml
   rke2_airgap: true
   rke2_airgap_images_path: "/opt/rke2-artifacts"
   ```

4. **Run install** as normal:
   ```bash
   ansible-playbook playbooks/install.yml -i environments/my-cluster/inventory/hosts.yml
   ```

**Airgap upgrades** need the new artifacts staged before the service is stopped.
Point `rke2_airgap_local_artifacts` at a controller-side directory holding the
tarballs for the target `rke2_version`; the play copies them to the node and
refuses to continue unless the staged `sha256sum-amd64.txt` matches. Without it,
`install.sh` would re-run against the artifacts already on the node and
reinstall the version you are trying to leave.

## Adding a New Cluster

```bash
cp -r environments/example environments/my-cluster
# Edit hosts, IPs, and overrides
```

Only override what differs from `roles/rke2_common/defaults/main.yml`.

## Security

### General

- Use SSH keys instead of passwords for authentication
- Use `ansible-vault` to encrypt any sensitive variables
- Change all default passwords (`haproxy_stats_password`, `keepalived_auth_pass`)
- Never commit credentials to version control

### Using Ansible Vault

Encrypt sensitive variables per-environment:

```bash
# Create encrypted secrets file
ansible-vault create environments/my-cluster/inventory/group_vars/vault.yml
```

```yaml
# vault.yml (encrypted)
vault_haproxy_stats_password: "my-secure-password"
vault_keepalived_auth_pass: "k8sHA01"
vault_rke2_etcd_s3_access_key: "AKIA..."
vault_rke2_etcd_s3_secret_key: "wJal..."
```

Reference vault variables in `group_vars/all.yml` or `loadbalancers.yml`:

```yaml
# loadbalancers.yml
haproxy_stats_password: "{{ vault_haproxy_stats_password }}"
keepalived_auth_pass: "{{ vault_keepalived_auth_pass }}"
```

```yaml
# all.yml
rke2_etcd_s3_access_key: "{{ vault_rke2_etcd_s3_access_key }}"
rke2_etcd_s3_secret_key: "{{ vault_rke2_etcd_s3_secret_key }}"
```

Run playbooks with `--ask-vault-pass` or `--vault-password-file`:

```bash
ansible-playbook playbooks/install.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  --ask-vault-pass
```

See [docs/vault-guide.md](docs/vault-guide.md) for SOPS integration and CI/CD patterns.

## Failure and Rollback

### Upgrade failure

If a rolling upgrade fails mid-way:
- The failed node is automatically **uncordoned** (block/rescue pattern)
- Already-upgraded nodes remain on the new version
- Non-upgraded nodes stay on the old version
- RKE2 supports mixed-version clusters within one minor version

**To retry:** fix the issue and re-run the upgrade playbook. Nodes already on
`rke2_version` are re-run but the install script is a no-op for them, and the
run asserts the version afterwards, so a node that did not take is reported
rather than skipped silently.

### etcd restore failure

If etcd restore fails:
- All masters are stopped (by design)
- Re-run the restore playbook to retry
- If the cluster is unrecoverable, use `uninstall.yml` and re-deploy from scratch

### Node failure

If a node becomes unresponsive:
1. Remove it from the cluster: `ansible-playbook playbooks/remove_node.yml -e "node_name=<name>"`
2. Fix or replace the node
3. Re-add it: `ansible-playbook playbooks/add_node.yml -e "target_hosts=<host>"`

## Day-2 Operations

| Operation | Guide |
|-----------|-------|
| Upgrade pre-flight checklist | [docs/upgrade-checklist.md](docs/upgrade-checklist.md) |
| Backup and restore runbook | [docs/backup-restore-runbook.md](docs/backup-restore-runbook.md) |
| Vault and secrets management | [docs/vault-guide.md](docs/vault-guide.md) |

## Requirements

- ansible-core >= 2.19
- Python >= 3.11 on the control node
- Target nodes: RHEL/Rocky/AlmaLinux 9, Ubuntu 22.04/24.04, Debian 12
- SSH access with sudo privileges

## Acknowledgements

This project was developed with the assistance of [Claude Code](https://claude.ai) (Opus 4.6).

## License

Apache License 2.0
