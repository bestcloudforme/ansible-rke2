# Secrets Management with Ansible Vault

## Overview

This project handles sensitive data (tokens, passwords, S3 credentials) throughout its lifecycle. All secret-handling tasks use `no_log: true` and `diff: false` to prevent exposure in Ansible output. However, you must also protect secrets at rest in your inventory files.

## Recommended Setup

### 1. Create Encrypted Secrets File

```bash
ansible-vault create environments/my-cluster/inventory/group_vars/vault.yml
```

### 2. Define Secrets in vault.yml

```yaml
# environments/my-cluster/inventory/group_vars/vault.yml (encrypted)

# HAProxy (only needed for rke2_lb_type: haproxy)
vault_haproxy_stats_password: "your-strong-password"
vault_keepalived_auth_pass: "k8sHA01"   # max 8 characters

# S3 etcd backup (only needed if rke2_etcd_s3_enabled: true)
vault_rke2_etcd_s3_access_key: "AKIAIOSFODNN7EXAMPLE"
vault_rke2_etcd_s3_secret_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

### 3. Reference in Group Vars

```yaml
# environments/my-cluster/inventory/group_vars/loadbalancers.yml
haproxy_stats_password: "{{ vault_haproxy_stats_password }}"
keepalived_auth_pass: "{{ vault_keepalived_auth_pass }}"
```

```yaml
# environments/my-cluster/inventory/group_vars/all.yml
rke2_etcd_s3_access_key: "{{ vault_rke2_etcd_s3_access_key }}"
rke2_etcd_s3_secret_key: "{{ vault_rke2_etcd_s3_secret_key }}"
```

### 4. Run Playbooks

```bash
# Interactive password prompt
ansible-playbook playbooks/install.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  --ask-vault-pass

# Password file (for automation/CI)
ansible-playbook playbooks/install.yml \
  -i environments/my-cluster/inventory/hosts.yml \
  --vault-password-file ~/.vault_pass
```

## Vault Password File

For CI/CD pipelines, store the vault password in a file:

```bash
# Create password file (NOT committed to git)
echo "your-vault-password" > ~/.vault_pass
chmod 600 ~/.vault_pass
```

Add to `ansible.cfg` to avoid passing `--vault-password-file` every time:

```ini
[defaults]
vault_password_file = ~/.vault_pass
```

**Important:** Add the password file to `.gitignore`:

```gitignore
.vault_pass
*vault_pass*
```

## Editing Encrypted Files

```bash
# Edit existing vault file
ansible-vault edit environments/my-cluster/inventory/group_vars/vault.yml

# View without editing
ansible-vault view environments/my-cluster/inventory/group_vars/vault.yml

# Re-key (change vault password)
ansible-vault rekey environments/my-cluster/inventory/group_vars/vault.yml
```

## SOPS Alternative

If you prefer [Mozilla SOPS](https://github.com/getsops/sops) with cloud KMS:

1. Install SOPS and configure your KMS key
2. Encrypt the secrets file:
   ```bash
   sops environments/my-cluster/inventory/group_vars/secrets.yml
   ```
3. Use the [community.sops](https://github.com/ansible-collections/community.sops) collection to decrypt at runtime

## What Secrets Does This Project Handle?

| Secret | Used By | Variable |
|--------|---------|----------|
| RKE2 cluster join token | Server/agent join | `rke2_server_token` (auto-generated) |
| HAProxy stats password | HAProxy stats page | `haproxy_stats_password` |
| Keepalived auth password | VRRP authentication | `keepalived_auth_pass` |
| S3 access key | etcd S3 backup | `rke2_etcd_s3_access_key` |
| S3 secret key | etcd S3 backup | `rke2_etcd_s3_secret_key` |

The RKE2 join token is automatically read from the bootstrap master and passed via `no_log: true` set_fact. You do not need to manage it manually.

## File Structure Example

```
environments/my-cluster/
├── cluster.yml
└── inventory/
    ├── hosts.yml
    └── group_vars/
        ├── all.yml                # Plain-text cluster config
        ├── masters.yml            # Plain-text master config
        ├── workers.yml            # Plain-text worker config
        ├── loadbalancers.yml      # References vault_ prefixed vars
        └── vault.yml              # Encrypted with ansible-vault
```
