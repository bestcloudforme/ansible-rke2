# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-03-24

### Added
- Compatibility matrix in README (tested Ansible, OS, RKE2 versions)
- Network port requirements table in README
- Airgap artifact preparation guide in README
- Failure and rollback documentation in README
- Day-2 operations section with links to runbooks
- `docs/upgrade-checklist.md` - Pre/post upgrade checklist
- `docs/backup-restore-runbook.md` - Full backup and restore runbook with node replacement
- `docs/vault-guide.md` - Ansible Vault and SOPS secrets management guide
- Vault usage examples in README security section
- Group vars structure documentation in README
- Minimum hardware requirements in README

### Changed
- Pinned collection versions in `requirements.yml` (bounded upper ranges)
- Upgrade playbooks now use `block/rescue` to auto-uncordon on failure
- Cordon/drain tasks now use `failed_when` instead of `changed_when: true`
- CNI verification checks now require at least 1 pod before passing
- S3 credentials passed via environment variables instead of CLI arguments
- HAProxy validation split into individual asserts with specific error messages
- Cilium operator replicas auto-scale to 2 for HA clusters
- Example passwords changed from `ch4ng3m3` to `CHANGEME` for clarity
- Kubelet resource reservations support partial config (CPU-only or memory-only)
- etcd user home path set to `/var/lib/etcd` for CIS compliance
- kube-vip container now has resource limits

### Removed
- Dead duplicate Cilium template from `roles/cni/templates/`

## [1.1.0] - 2026-03-24

### Added
- etcd backup playbook with local and S3 snapshot support
- etcd restore playbook (stops masters, restores, rejoins)
- Certificate rotation playbook (serial master rotation + worker restart)
- Kubeconfig download playbook (rewrites server URL for external access)
- CIS hardening profile support (`rke2_cis_profile` variable)
- etcd S3 backup variables (`rke2_etcd_s3_*`)
- Ansible Galaxy metadata (`galaxy.yml`)
- `.gitignore` entries for kubeconfig and Galaxy artifacts
- `etcd` system user creation for CIS compliance in preflight

## [1.0.0] - 2026-03-24

### Added
- Initial release
- RKE2 cluster deployment (single master and HA)
- HAProxy + keepalived load balancer role
- kube-vip and external LB support
- Rolling upgrade with drain/uncordon
- Add/remove node playbooks
- Full uninstall playbook
- RHEL and Debian support
- Airgap installation support
- EKS Distro image override
- Production hardening: etcd snapshots, audit logging, PSA, resource reservations
- Canal, Calico, and Cilium CNI support
- Multi-cluster environment structure
- Example environments (single-master and HA)
