# ansible-rke2

Production-ready Ansible playbooks for deploying RKE2 Kubernetes clusters. Supports single-master dev setups and full HA production clusters with HAProxy + keepalived.

## Features

- **Full Lifecycle**: install, upgrade, add/remove nodes, uninstall, etcd backup/restore, cert rotation
- **HA Support**: 3-master clusters with HAProxy + keepalived VIP, or kube-vip, or external LB
- **CIS Hardening**: Optional CIS 1.23 benchmark profile for security compliance
- **Multi-OS**: RHEL/Rocky/AlmaLinux 8+ and Ubuntu/Debian 20.04+
- **CNI Choice**: Canal, Calico, or Cilium (with kube-proxy replacement and BPF masquerade)
- **Airgap**: Online and offline installation support
- **EKS Distro**: Private registry mirror for EKS-D images
- **Custom Manifests**: Auto-deploy custom Kubernetes manifests on server start
- **Production Hardening**: etcd snapshots, audit logging, Pod Security Admission, resource reservations, kernel hardening, system limits, log rotation
- **Multi-Environment**: Shared roles, per-cluster environment configs
- **Rolling Upgrades**: Masters serial:1, workers serial:25% with drain/uncordon

## Compatibility Matrix

| Component | Tested Versions |
|-----------|----------------|
| **Ansible** | 2.15, 2.16, 2.17 (ansible-core) |
| **Python** | 3.9, 3.10, 3.11, 3.12 |
| **RKE2** | v1.28.x, v1.29.x, v1.30.x, v1.31.x, v1.32.x |
| **RHEL/Rocky/Alma** | 8.x, 9.x |
| **Ubuntu** | 20.04, 22.04, 24.04 |
| **Debian** | 11 (Bullseye), 12 (Bookworm) |

**Required Ansible Collections:**

| Collection | Version Range |
|-----------|---------------|
| `ansible.posix` | >= 1.5, < 2.0 |
| `community.general` | >= 7.0, < 10.0 |

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
├── defaults/rke2_defaults.yml          # All default variables (single source of truth)
├── docs/                               # Operational runbooks and guides
│   ├── upgrade-checklist.md
│   ├── backup-restore-runbook.md
│   └── vault-guide.md
├── environments/
│   ├── example/                        # Single-master example
│   │   ├── inventory/
│   │   │   ├── hosts.yml
│   │   │   └── group_vars/
│   │   └── cluster.yml                # Cluster metadata (name, env, notes)
│   └── ha-example/                     # HA cluster example (3 master + HAProxy)
│       ├── inventory/
│       │   ├── hosts.yml
│       │   └── group_vars/
│       │       ├── all.yml             # Cluster-wide vars
│       │       ├── masters.yml         # Master-specific vars
│       │       ├── workers.yml         # Worker-specific vars
│       │       └── loadbalancers.yml   # HAProxy/keepalived vars
│       └── cluster.yml                # Cluster metadata (name, env, notes)
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
└── roles/
    ├── preflight/                      # OS prerequisites (kernel modules, sysctl, packages)
    ├── rke2_server/                    # Master node installation and config
    ├── rke2_agent/                     # Worker node installation and config
    ├── cni/                            # CNI verification (canal/calico/cilium)
    ├── lb/                             # kube-vip or external LB setup
    ├── haproxy/                        # HAProxy + keepalived for HA
    ├── eksd_images/                    # EKS Distro image configuration
    └── lifecycle/                      # Upgrade, remove, uninstall operations
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
| 10255 | TCP | All nodes | kubelet read-only |
| 179 | TCP | All nodes | BGP (Calico only) |
| 4240 | TCP | All nodes | Cilium health check (Cilium only) |
| 8090 | TCP | All nodes | Cilium Hubble (Cilium only) |

**HAProxy nodes (when `rke2_lb_type: haproxy`):**

| Port | Protocol | Purpose |
|------|----------|---------|
| 6443 | TCP | API frontend (proxied to masters) |
| 9345 | TCP | Join frontend (proxied to masters) |
| 9000 | TCP | HAProxy stats page |

**Firewall handling:**

- **RHEL/Rocky/Alma**: The `preflight` role opens ports via `firewalld` if the service is active. If `firewalld` is not running, ports are not managed.
- **Ubuntu/Debian**: The `preflight` role opens ports via `ufw` if the service is active. If `ufw` is not running, ports are not managed.
- If you use a different firewall solution, open the ports listed above manually before running the install playbook.

## Playbooks

### Install

```bash
ansible-playbook playbooks/install.yml \
  -i environments/my-cluster/inventory/hosts.yml
```

Execution order:
1. HAProxy load balancers (if `rke2_lb_type: haproxy`)
2. OS prerequisites on all nodes
3. Production hardening configs (audit policy, PSA)
4. kube-vip manifest (if applicable)
5. Masters (serial: 1)
6. EKS-D images (optional)
7. Workers
8. CNI verification

### Upgrade

```bash
ansible-playbook playbooks/upgrade.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_version=v1.33.0+rke2r1"
```

Rolling upgrade with cordon/drain/uncordon. Masters upgraded one at a time, workers at 25%. If an upgrade fails mid-flight, the node is automatically uncordoned.

**Note:** Drain/uncordon operations use `ansible_hostname` as the Kubernetes node name. Ensure the OS hostname matches the Kubernetes node name (default RKE2 behavior).

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
  -e "rke2_etcd_backup_name=pre-upgrade-v1.33"
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
rke2_vip_interface: "eth0"
```

**HA with kube-vip:**
```yaml
# group_vars/all.yml
rke2_master_count: 3
rke2_lb_type: "kube-vip"
rke2_lb_vip: "192.168.1.100"
rke2_vip_interface: "eth0"
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

All defaults are in `defaults/rke2_defaults.yml`. Override per-environment in `group_vars/`.

| Variable | Default | Description |
|----------|---------|-------------|
| **Core** | | |
| `rke2_version` | *(required)* | RKE2 version (e.g. `v1.32.2+rke2r1`) |
| `rke2_cni` | `canal` | CNI plugin: `canal`, `calico`, `cilium` |
| `rke2_master_count` | `1` | Number of masters: `1` or `3` |
| `rke2_channel` | `stable` | RKE2 release channel |
| `rke2_cluster_cidr` | `10.42.0.0/16` | Pod network CIDR |
| `rke2_service_cidr` | `10.43.0.0/16` | Service network CIDR |
| `rke2_cilium_kube_proxy_replacement` | `true` | Replace kube-proxy with Cilium eBPF (when cni=cilium) |
| `rke2_cilium_bpf_masquerade` | `true` | Use BPF masquerading (when cni=cilium) |
| `rke2_custom_manifests` | `[]` | List of local manifest paths to auto-deploy |
| **Load Balancer** | | |
| `rke2_lb_type` | `external` | LB type: `kube-vip`, `external`, `haproxy` |
| `rke2_lb_vip` | `""` | Virtual IP (required for kube-vip/haproxy) |
| `rke2_lb_external_host` | `""` | External LB host (required for external) |
| `rke2_vip_interface` | `eth0` | Network interface for VIP |
| `rke2_server_tls_san` | `[]` | Additional TLS SANs for API server |
| **HAProxy** | | |
| `haproxy_stats_password` | `changeme` | Stats page password (MUST change) |
| `haproxy_balance_algorithm` | `roundrobin` | Backend balance algorithm |
| `haproxy_maxconn` | `3000` | Max connections |
| `keepalived_auth_pass` | `rke2ha` | VRRP auth (max 8 chars) |
| `keepalived_vrrp_id` | `51` | VRRP virtual router ID |
| **Hardening** | | |
| `rke2_etcd_snapshot_schedule` | `""` | Cron schedule for etcd snapshots |
| `rke2_etcd_snapshot_retention` | `5` | Number of snapshots to keep |
| `rke2_audit_policy_enabled` | `false` | Enable API server audit logging |
| `rke2_audit_log_maxage` | `30` | Audit log max age in days |
| `rke2_pod_security_admission` | `""` | PSA level: `restricted`, `baseline`, `privileged` |
| `rke2_kube_reserved_cpu` | `""` | CPU reserved for kubelet |
| `rke2_kube_reserved_memory` | `""` | Memory reserved for kubelet |
| `rke2_system_reserved_cpu` | `""` | CPU reserved for system |
| `rke2_system_reserved_memory` | `""` | Memory reserved for system |
| `rke2_eviction_hard` | `""` | Kubelet eviction thresholds (e.g. `memory.available<256Mi`) |
| `rke2_protect_kernel_defaults` | `false` | Enforce kubelet kernel parameters |
| `rke2_cis_profile` | `""` | CIS hardening profile: `cis` or `cis-1.23` |
| **etcd S3 Backup** | | |
| `rke2_etcd_s3_enabled` | `false` | Enable S3 backend for etcd snapshots |
| `rke2_etcd_s3_endpoint` | `""` | S3 endpoint (e.g. `s3.amazonaws.com`) |
| `rke2_etcd_s3_bucket` | `""` | S3 bucket name |
| `rke2_etcd_s3_region` | `""` | S3 region |
| `rke2_etcd_s3_access_key` | `""` | S3 access key (use vault!) |
| `rke2_etcd_s3_secret_key` | `""` | S3 secret key (use vault!) |
| `rke2_etcd_s3_folder` | `""` | S3 prefix/folder |
| `rke2_server_node_taints` | `[]` | Taints for master nodes |
| `rke2_server_node_labels` | `[]` | Labels for master nodes |
| `rke2_agent_node_labels` | `[]` | Labels for worker nodes |
| **Airgap** | | |
| `rke2_airgap` | `false` | Enable airgap installation |
| `rke2_airgap_images_path` | `/opt/rke2-artifacts` | Path to airgap artifacts |
| `rke2_registry_mirror` | `""` | Private registry mirror URL |
| **EKS Distro** | | |
| `eksd_enabled` | `false` | Enable EKS-D image override |
| `eksd_version` | `1-32-eks-1` | EKS-D release version |
| **Lifecycle** | | |
| `rke2_drain_timeout` | `300s` | Node drain timeout |
| `rke2_upgrade_serial` | `1` | Master upgrade serial count |
| `rke2_upgrade_agent_serial` | `25%` | Worker upgrade batch percentage |
| `rke2_reboot_after_uninstall` | `false` | Reboot nodes after uninstall |

## Airgap Installation

For airgap (offline) environments:

1. **Download artifacts** on an internet-connected machine:
   ```bash
   # Download RKE2 artifacts for your target version
   RKE2_VERSION="v1.32.2+rke2r1"
   mkdir -p rke2-artifacts && cd rke2-artifacts
   curl -LO "https://github.com/rancher/rke2/releases/download/${RKE2_VERSION}/rke2-images.linux-amd64.tar.zst"
   curl -LO "https://github.com/rancher/rke2/releases/download/${RKE2_VERSION}/rke2.linux-amd64.tar.gz"
   curl -LO "https://github.com/rancher/rke2/releases/download/${RKE2_VERSION}/sha256sum-amd64.txt"
   curl -LO "https://get.rke2.io" -o install.sh && chmod +x install.sh
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

## Adding a New Cluster

```bash
cp -r environments/example environments/my-cluster
# Edit hosts, IPs, and overrides
```

Only override what differs from `defaults/rke2_defaults.yml`.

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

**To retry:** Fix the issue and re-run the upgrade playbook. It will skip already-upgraded nodes.

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

- Ansible >= 2.15 (ansible-core)
- Python >= 3.9
- Target nodes: RHEL/Rocky/AlmaLinux 8+ or Ubuntu 20.04+ or Debian 11+
- SSH access with sudo privileges
- Minimum 2 CPU, 4 GB RAM per node (4 CPU, 8 GB recommended for masters)

## Acknowledgements

This project was developed with the assistance of [Claude Code](https://claude.ai) (Opus 4.6).

## License

Apache License 2.0
