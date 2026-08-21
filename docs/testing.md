# Testing

What this collection is actually tested against, and what it is not.

## Automated, on every pull request

`.github/workflows/lint.yml` runs:

| Check | What it catches |
|-------|-----------------|
| `yamllint .` | formatting, syntax |
| `ansible-lint` | task-level defects, unresolvable `hosts:` patterns |
| `--syntax-check` on all 9 playbooks × both example inventories | broken includes, bad play structure |
| `tests/vars-precedence.yml` | a `vars_files` regression that would silently discard every `group_vars` override |

`--syntax-check` cannot catch variable-resolution bugs — the playbooks parsed
fine for months while `group_vars` was being ignored entirely. That is why the
precedence test exists as a separate gate.

## Manual, before a release

A 3-master HA cluster on real hosts, both OS families, from wiped nodes:

| | |
|---|---|
| Topology | 3 masters + 2 workers + 2 load balancers |
| OS | Rocky Linux 9.8, Ubuntu 24.04 LTS |
| RKE2 | v1.35.7+rke2r1, upgraded to v1.36.3+rke2r1 |
| CNI | Canal, Calico |
| Load balancer | HAProxy + keepalived with a VIP |
| Hardening | `rke2_cis_profile: cis`, `protect-kernel-defaults`, audit policy, Pod Security Admission |

Exercised end to end:

- `install.yml` from scratch, then re-run to confirm `changed=0`
- `upgrade.yml` across a minor version, all five nodes, no node left cordoned
- Config-change handling: a `tls-san` edit restarts every server cleanly
- Firewall rules land on both `firewalld` and `ufw`, including the pod and
  service CIDRs
- The VIP serves both `6443` and `9345`, and the keepalived interface is
  autodetected (`eth0` on Rocky, `ens5` on Ubuntu)

## Not covered

Be aware of these before relying on them in production:

- **`rke2_lb_type: kube-vip`.** The manifest is written to kube-vip's current
  documented control-plane configuration, but it has not run on a live cluster.
  It cannot be validated on EC2: AWS does not route an address that is not
  assigned to an ENI, so no ARP-based VIP works there regardless of correctness.
  Test it on a network that honours gratuitous ARP.
- **Airgap install and upgrade.** The staging and version assertions are in
  place; the flow itself has not been run against a real artifact mirror.
- **`etcd_restore.yml`.** Destructive by nature and not exercised. Read
  [backup-restore-runbook.md](backup-restore-runbook.md) and rehearse it on a
  throwaway cluster before you need it.
- **EKS-D image mirroring.**
- **RHEL 8 and Debian.** Only Rocky 9 and Ubuntu 24.04 were used.
- **Single-master (`environments/example`).** Only the HA topology was built on
  real hosts; the single-master path is covered by syntax and lint checks.

## Reproducing the manual run

Any 7 hosts reachable over SSH with passwordless sudo will do. Copy
`environments/ha-example`, point the inventory at them, set `rke2_version`, and:

```bash
ansible-playbook playbooks/install.yml -i environments/my-cluster/inventory/hosts.yml
ansible-playbook playbooks/install.yml -i environments/my-cluster/inventory/hosts.yml   # expect changed=0
ansible-playbook playbooks/upgrade.yml -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_version=<next minor>"
```

Check afterwards that no node is left `SchedulingDisabled`:

```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,VERSION:.status.nodeInfo.kubeletVersion,UNSCHED:.spec.unschedulable
```
