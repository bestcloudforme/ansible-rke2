# Upgrade Checklist

Pre-flight checklist before running `playbooks/upgrade.yml`.

## Before You Start

- [ ] Read the [RKE2 release notes](https://github.com/rancher/rke2/releases) for the target version
- [ ] Verify the upgrade path is one minor version. `upgrade.yml` refuses a
      bigger jump, and refuses downgrades - Kubernetes supports neither
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
1. Masters are upgraded one at a time: check the other control-plane nodes are
   Ready, cordon, drain, stop, upgrade, start, wait Ready, assert the version,
   uncordon
2. Workers are upgraded in batches of 25% (same cordon/drain/upgrade/uncordon flow)
3. If any step fails the node is uncordoned - unless it was already cordoned
   before the run, in which case it is left as the operator set it

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
     -e "rke2_etcd_restore_snapshot=pre-upgrade-$(date +%Y%m%d)"
   ```
4. RKE2 and Kubernetes do not support downgrades. Restore etcd from the
   pre-upgrade snapshot and rebuild the nodes at the original version;
   `install.yml` will refuse to run against a node whose installed version does
   not match `rke2_version`

## Airgap

An airgap upgrade needs the artifacts for the target version staged before the
service stops. Set `rke2_airgap_local_artifacts` to a controller-side directory
holding the `rke2_version` tarballs, `sha256sum-amd64.txt` and `install.sh`. The
play copies them to `rke2_airgap_images_path` and asserts the staged checksum
file matches `rke2_version` before stopping anything.

Without it the install script re-runs against whatever is already on the node
and reinstalls the version you are trying to leave.
