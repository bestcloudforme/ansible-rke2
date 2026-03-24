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
├── environments/
│   ├── example/                        # Single-master example
│   │   ├── inventory/
│   │   │   ├── hosts.yml
│   │   │   └── group_vars/
│   │   └── cluster.yml
│   └── ha-example/                     # HA cluster example (3 master + HAProxy)
│       ├── inventory/
│       │   ├── hosts.yml
│       │   └── group_vars/
│       └── cluster.yml
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

Rolling upgrade with drain/uncordon. Masters upgraded one at a time, workers at 25%.

**Note:** Drain/uncordon operations use `ansible_hostname` as the Kubernetes node name. Ensure the OS hostname matches the Kubernetes node name (default RKE2 behavior).

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

## Adding a New Cluster

```bash
cp -r environments/example environments/my-cluster
# Edit hosts, IPs, and overrides
```

Only override what differs from `defaults/rke2_defaults.yml`.

## Security Notes

- Use SSH keys instead of passwords for authentication
- Use `ansible-vault` to encrypt any sensitive variables
- Change all default passwords (`haproxy_stats_password`, `keepalived_auth_pass`)
- Never commit credentials to version control

## Requirements

- Ansible >= 2.15
- Python >= 3.9
- Target nodes: RHEL/Rocky/AlmaLinux 8+ or Ubuntu 20.04+
- SSH access with sudo privileges

## License

Apache License 2.0
