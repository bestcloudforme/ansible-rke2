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
- Fork the repository
- Create a feature branch
- Test your changes
- Run linting: `yamllint .` and `ansible-lint`
- Submit a PR with a clear description

## Code Style

- Follow Ansible best practices
- Use FQCN (Fully Qualified Collection Names) for all modules
- Keep tasks idempotent
- Add `changed_when` to command/shell tasks
- Use `ansible.builtin.` prefix for all built-in modules
