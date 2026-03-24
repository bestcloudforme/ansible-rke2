# Backup and Restore Runbook

## Backup Strategy

### Automated Snapshots

RKE2 can take periodic etcd snapshots automatically. Configure in `group_vars/all.yml`:

```yaml
rke2_etcd_snapshot_schedule: "0 */6 * * *"   # Every 6 hours
rke2_etcd_snapshot_retention: 10              # Keep last 10 snapshots
```

Snapshots are stored at: `/var/lib/rancher/rke2/server/db/snapshots/`

### Manual Backup

```bash
# Local snapshot with auto-generated name
ansible-playbook playbooks/etcd_backup.yml \
  -i environments/my-cluster/inventory/hosts.yml

# Named snapshot (recommended before upgrades/changes)
ansible-playbook playbooks/etcd_backup.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_etcd_backup_name=pre-upgrade-v1.33"
```

### S3 Backup

Configure S3 variables in `group_vars/all.yml` (use `ansible-vault` for credentials):

```yaml
rke2_etcd_s3_enabled: true
rke2_etcd_s3_endpoint: "s3.amazonaws.com"
rke2_etcd_s3_bucket: "my-etcd-backups"
rke2_etcd_s3_region: "eu-west-1"
rke2_etcd_s3_access_key: "{{ vault_rke2_etcd_s3_access_key }}"
rke2_etcd_s3_secret_key: "{{ vault_rke2_etcd_s3_secret_key }}"
rke2_etcd_s3_folder: "my-cluster"
```

S3 credentials are passed via environment variables (not CLI args) for security.

### Listing Snapshots

SSH to any master and run:

```bash
/var/lib/rancher/rke2/bin/rke2 etcd-snapshot list
```

## Restore

**Warning:** Restore is a destructive operation. It stops ALL masters, resets etcd on the bootstrap master, and rejoins other masters. Workloads on workers are not affected but will briefly lose API connectivity.

### Pre-Restore Checklist

- [ ] Confirm the snapshot name/path
- [ ] Notify users about planned downtime
- [ ] Ensure SSH access to all masters
- [ ] Verify the snapshot is not corrupted (check file size, timestamp)

### Restore from Local Snapshot

```bash
# List available snapshots on the bootstrap master
ssh master01 '/var/lib/rancher/rke2/bin/rke2 etcd-snapshot list'

# Restore
ansible-playbook playbooks/etcd_restore.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_etcd_restore_snapshot=/var/lib/rancher/rke2/server/db/snapshots/my-snapshot"
```

### Restore from S3

```bash
ansible-playbook playbooks/etcd_restore.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  -e "rke2_etcd_restore_snapshot=my-snapshot-name" \
  --ask-vault-pass
```

### What Happens During Restore

1. **Validate** — Checks snapshot name is provided
2. **Stop ALL masters** — All rke2-server services are stopped simultaneously
3. **Restore etcd** — Runs `rke2 server --cluster-reset` on the bootstrap master only
4. **Start bootstrap master** — Waits for API on port 6443
5. **Rejoin other masters** — Clears old etcd data, starts rke2-server one at a time
6. **Verify** — Waits for all masters to report Ready

### Post-Restore

- [ ] Verify all masters are Ready: `kubectl get nodes`
- [ ] Verify workers reconnect: `kubectl get nodes` (workers may take 1-2 minutes)
- [ ] Check workload health: `kubectl get pods -A`
- [ ] Take a fresh backup to confirm the restore point

## Node Replacement

If a node needs to be replaced (hardware failure, OS corruption):

1. **Remove the failed node:**
   ```bash
   ansible-playbook playbooks/remove_node.yml \
     -i environments/my-cluster/inventory/hosts.yml \
     -e "node_name=worker-3"
   ```

2. **Provision a new node** with the same OS and SSH access

3. **Update inventory** — Replace the old IP/hostname with the new one

4. **Add the new node:**
   ```bash
   ansible-playbook playbooks/add_node.yml \
     -i environments/my-cluster/inventory/hosts.yml \
     -e "target_hosts=worker-3"
   ```
