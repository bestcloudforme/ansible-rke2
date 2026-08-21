# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-08-21

### Changed

- **Pod Security Admission exemptions are configurable** through
  `rke2_pod_security_exemptions`. The template hardcoded `monitoring` and
  `logging` - permanent exemptions for namespaces that may not exist - and
  omitted `calico-system`, which RKE2's Calico needs. If you relied on the old
  `monitoring`/`logging` entries, set them explicitly.

### Fixed

- Documentation matched a repository that no longer existed. 62 mismatches, 40
  in the README: the directory tree, the install execution order, the airgap
  `curl` command that never produced `install.sh`, an upgrade-retry claim that
  was never true, and a variable table missing 54 of the 113 variables the roles
  define.

### Added

- `tests/docs-match-code.py`, run in CI. Fails on an undocumented variable, a
  documented variable that does not exist, a path named in a doc that is absent,
  or a broken relative link.

## [2.0.0] - 2026-08-21

A correctness release. The collection could not deploy a cluster as documented
before this: `install.yml` failed its own `rke2_version` assert on both shipped
example inventories.

### Breaking

- **Set `rke2_version` explicitly and step through minors one at a time.**
  `upgrade.yml` now refuses a jump of more than one minor, and refuses
  downgrades. Kubernetes does not support either.
- **Collections bumped**: `ansible.posix` >= 2.2.0, `community.general` >= 13.0.0.
  Re-run `ansible-galaxy collection install -r requirements.yml`. Airgap bundles
  also need `community.library_inventory_filtering_v1`, a transitive dependency
  of community.general 13.
- **ansible-core floor is 2.19.** RHEL 8 controllers and most distro-packaged
  Ansible are below it.
- **`ansible.cfg` no longer uses the `yaml` stdout callback.** It was removed in
  community.general 12.0.0 and is a hard error there. If you set
  `ANSIBLE_STDOUT_CALLBACK=yaml` yourself, drop it.
- **`defaults/rke2_defaults.yml` moved to `roles/rke2_common/defaults/main.yml`.**
  If you pointed your own `vars_files` at the old path, update it.
- **The first `install.yml` run after upgrading restarts rke2-server on every
  master.** Any change to `config.yaml` does, and this release changes several
  keys. Plan a window.
- **`disable-kube-proxy: true` on an existing Cilium cluster is a datapath
  cutover.** kube-proxy was running alongside Cilium's replacement; removing it
  does not clean up its iptables rules. Drain, apply, then reboot the node.
- **kube-vip's DaemonSet selector and env changed**, and it now actually
  advertises the VIP. If a VIP appears to work today, something other than
  kube-vip is advertising it - resolve that before applying, or you get an
  address conflict. Delete the old DaemonSet first:
  `kubectl delete ds -n kube-system kube-vip-ds`.
- **keepalived now starts as BACKUP everywhere with priority deciding**, and a
  failed check releases the VIP instead of nudging the priority. Rolling this out
  causes at least one failover.
- **`rke2_cis_profile` accepts only `cis` or `etcd`.** `cis-1.23` was a fatal RKE2
  startup error; it is now an Ansible assert at preflight.
- **CIS sysctls change host behaviour**: `kernel.panic=10` and
  `kernel.panic_on_oops=1` mean the node reboots on an oops. Applied only when
  `rke2_protect_kernel_defaults` or `rke2_cis_profile` is set.
- **Pod Security Admission exemptions are configurable** via
  `rke2_pod_security_exemptions`. The template hardcoded `monitoring` and
  `logging` - permanent holes in the policy for namespaces that may not exist -
  and omitted `calico-system`, which RKE2's Calico needs.
- **`ip_vs*` modules are no longer loaded by default.** Set
  `preflight_load_ipvs_modules: true` if you run kube-proxy in IPVS mode.
- **SELinux is no longer forced to permissive.** `preflight_selinux_state` is
  empty by default and leaves the host alone.
- **`eksd_version` removed** - nothing ever read it. `rke2_node_address` was
  added and removed within this release and never shipped.

### Fixed

- Shared defaults are role defaults, so `group_vars` overrides them. They were
  loaded with play-level `vars_files`, which outranks inventory - every
  per-environment value was silently discarded.
- The `rke2` CLI is resolved per OS family. `rke2_bin_dir` holds kubectl, not
  the CLI, so etcd backup, etcd restore and certificate rotation each failed on
  their first command. Restore left every master stopped.
- Nodes are looked up by their full hostname. `ansible_hostname` truncates the
  FQDN that RHEL cloud images use, so every cordon, drain and readiness wait
  missed.
- HAProxy starts on RHEL: 6443 and 9345 are labelled `http_port_t` and the unit
  gets a `RuntimeDirectory`. Neither existed, so the service could not bind.
- The keepalived health check works. It probed `/livez`, which RKE2 answers with
  401, so the check never passed and the VIP never failed over.
- HAProxy backends and keepalived peers resolve to the node's real address
  rather than its SSH address.
- CNI verification finds Calico. It looked in `kube-system`; RKE2 puts
  `calico-node` in `calico-system`, so every Calico install failed at Phase 6.
- `upgrade.yml` reaches the masters. It rendered `haproxy.cfg` outside the
  haproxy role, so every `haproxy_*` variable was undefined and `no_log` hid it.
- Service restarts tolerate RKE2 restarting itself under a slow apiserver.
- Cordon and drain are inside `block`/`rescue`; a stalled drain no longer leaves
  every worker cordoned.
- Airgap upgrades check the staged artifacts match `rke2_version` before
  stopping the service. They reinstalled the old version and reported success.
- `remove_node` works on a dead node, is re-runnable, and refuses to break etcd
  quorum.
- `uninstall` fails instead of reporting success when the scripts are missing,
  and removes the HAProxy systemd drop-in and SELinux port labels the role adds.
- etcd S3 settings reach the server config. Scheduled snapshots went to local
  disk regardless of `rke2_etcd_s3_*`.
- Audit records reach the host. `audit-policy-file` is a first-class RKE2 key;
  passed through `kube-apiserver-arg` the log stayed inside the static pod.
- `cluster-init` removed - RKE2 drops the flag and warns on every start.
- ufw rules are applied on Debian, and port ranges use ufw's colon syntax.
- `nm-cloud-setup.timer` is disabled, not just the service.
- The install script no longer lands in world-writable `/tmp`.
- The Lint workflow passes. It had never succeeded, so `ansible-lint` and all
  four syntax checks were skipped on every run.

### Added

- `roles/rke2_common` - shared defaults, a dependency of every role.
- `tests/vars-precedence.yml`, run in CI.
- `meta/runtime.yml`, and a `meta/main.yml` for every role.
- `docs/testing.md` - what is tested on real hosts and what is not.
- Preflight asserts for `rke2_cis_profile`, `rke2_cni`, `rke2_lb_type`, a single
  bootstrap master, and masters/workers overlap.
- `rke2_node_name`, `rke2_node_ip`, `rke2_node_external_ip`, `rke2_selinux`,
  `rke2_audit_log_dir`, `rke2_drain_force`, `rke2_install_bin_dir`, `rke2_cli`,
  `rke2_install_script`, `rke2_airgap_local_artifacts`, `rke2_api_ready_timeout`,
  `rke2_service_start_retries`, `rke2_pod_security_exemptions`,
  `preflight_selinux_state`, `preflight_firewalld_mode`,
  `preflight_load_ipvs_modules`, `cni_pod_selector`, `cni_wait_retries`,
  `haproxy_retries`, `haproxy_timeout_*`, `keepalived_priority`,
  `keepalived_unicast_src_ip`. The README table now lists every one.
- Firewall ports selected per node role and per CNI, plus the pod and service
  CIDRs in the trusted zone.

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
