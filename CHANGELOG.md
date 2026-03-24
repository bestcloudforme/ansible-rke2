# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
