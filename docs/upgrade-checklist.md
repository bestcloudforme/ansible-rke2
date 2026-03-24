# Upgrade Checklist

Pre-flight checklist before running `playbooks/upgrade.yml`.

## Before You Start

- [ ] Read the [RKE2 release notes](https://github.com/rancher/rke2/releases) for the target version
- [ ] Verify the upgrade path is supported (no more than 2 minor versions at a time)
- [ ] Confirm the target version is available: `curl -s https://update.rke2.io/v1-release/channels | jq`

## Pre-Upgrade

- [ ] **Take etcd backup:**
  ```bash
  ansible-playbook playbooks/etcd_backup.yml \
    -i environments/my-cluster/inventory/hosts.yml \
    -e "rke2_etcd_backup_name=pre-upgrade-$(date +%Y%m%d)"
  ```

- [ ] **Verify current cluster health:**
  ```bash
  kubectl get nodes
  kubectl get pods -A | grep -v Running | grep -v Completed
  kubectl get cs  # component status (deprecated but still useful)
  ```

- [ ] **Check for PodDisruptionBudgets that could block drain:**
  ```bash
  kubectl get pdb -A
  ```

- [ ] **Verify all nodes are Ready:**
  ```bash
  kubectl get nodes -o wide
  ```

- [ ] **Update inventory** with the new version:
  ```yaml
  # group_vars/all.yml
  rke2_version: "v1.33.0+rke2r1"
  ```

## Run Upgrade

```bash
ansible-playbook playbooks/upgrade.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_version=v1.33.0+rke2r1"
```

The upgrade process:
1. Masters are upgraded one at a time (cordon, drain, stop, upgrade, start, wait Ready, uncordon)
2. Workers are upgraded in batches of 25% (same cordon/drain/upgrade/uncordon flow)
3. If any step fails, the node is automatically uncordoned

## Post-Upgrade

- [ ] **Verify all nodes are on the new version:**
  ```bash
  kubectl get nodes -o wide
  ```

- [ ] **Check all system pods are healthy:**
  ```bash
  kubectl get pods -n kube-system
  ```

- [ ] **Verify CNI is working:**
  ```bash
  # Quick connectivity test
  kubectl run test-pod --image=busybox --rm -it --restart=Never -- wget -qO- http://kubernetes.default.svc
  ```

- [ ] **Take post-upgrade etcd backup:**
  ```bash
  ansible-playbook playbooks/etcd_backup.yml \
    -i environments/my-cluster/inventory/hosts.yml \
    -e "rke2_etcd_backup_name=post-upgrade-$(date +%Y%m%d)"
  ```

## Rollback

If the upgrade fails and you need to roll back:

1. The failed node is automatically uncordoned
2. Already-upgraded nodes stay on the new version (RKE2 supports mixed versions within one minor)
3. To fully roll back, restore the pre-upgrade etcd backup:
   ```bash
   ansible-playbook playbooks/etcd_restore.yml \
     -i environments/my-cluster/inventory/hosts.yml \
     -e "rke2_etcd_restore_snapshot=pre-upgrade-20260324"
   ```
4. Then re-run install with the original version to downgrade binaries
