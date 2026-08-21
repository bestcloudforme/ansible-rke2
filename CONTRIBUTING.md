# Contributing

This project is currently maintained by [@bcfmtolgahan](https://github.com/bcfmtolgahan).

## Bug Reports

If you find a bug, please open an issue with:
- Your environment (OS, Ansible version, RKE2 version)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs

## Feature Requests

Feature requests are welcome. Please open an issue describing:
- What you want to achieve
- Why existing features don't cover your use case

## Pull Requests

Pull requests are reviewed on a case-by-case basis. Before submitting:

- Fork the repository and create a feature branch
- Install the collection dependencies, which `ansible-lint` needs to resolve
  modules:
  ```bash
  ansible-galaxy collection install -r requirements.yml
  ```
- Run what CI runs:
  ```bash
  yamllint .
  ansible-lint
  ansible-playbook tests/vars-precedence.yml \
    -i environments/ha-example/inventory/hosts.yml -c local
  for pb in install upgrade remove_node uninstall etcd_backup \
            etcd_restore rotate_certs fetch_kubeconfig; do
    ansible-playbook playbooks/$pb.yml \
      -i environments/ha-example/inventory/hosts.yml --syntax-check
  done
  ```
- If you change anything that runs on a node, test it on a real cluster.
  `docs/testing.md` describes the topology used before a release, and records
  what is not covered.
- Submit a PR with a clear description of what breaks without the change

## Code Style

- FQCN for every module (`ansible.builtin.*`, `ansible.posix.*`, `community.general.*`)
- Keep tasks idempotent; `command`/`shell` tasks need `changed_when`, `creates`
  or `removes`
- Shared variables belong in `roles/rke2_common/defaults/main.yml`, not in a
  play's `vars_files` — play-level `vars_files` outranks inventory `group_vars`
  and would silently discard user overrides. `tests/vars-precedence.yml` guards
  this
- Cross-host lookups must read gathered facts, not role defaults: role defaults
  are play-scoped and do not appear in `hostvars[other_host]`
- Document any new user-facing variable in the README table
