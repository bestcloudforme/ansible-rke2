#!/usr/bin/env python3
"""Fail if the documentation has drifted from the code.

The README's variable table went stale silently once already. This checks the
claims a reader would act on:

  1. every variable in the README table exists in a role's defaults
  2. every variable defined in a role's defaults appears in the README table
  3. every repo path named in a doc exists
  4. every relative Markdown link resolves
  5. every playbook named in a doc exists

Run from the repository root:  python3 tests/docs-match-code.py
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "CHANGELOG.md"]
DOCS += sorted((ROOT / "docs").glob("*.md"))

# Variables that are set per host in the inventory rather than in role defaults.
INVENTORY_VARS = {"rke2_bootstrap"}

failures = []


def fail(doc, msg):
    failures.append(f"{doc.relative_to(ROOT)}: {msg}")


def code_variables():
    found = {}
    for f in sorted(ROOT.glob("roles/*/defaults/main.yml")):
        for key in (yaml.safe_load(f.read_text()) or {}):
            found[key] = f.relative_to(ROOT)
    return found


def check_variable_table(code):
    readme = ROOT / "README.md"
    documented = set(re.findall(r"^\| `([a-z][a-z0-9_]*)`", readme.read_text(), re.M))
    for name in sorted(documented - set(code) - INVENTORY_VARS):
        fail(readme, f"documents `{name}`, which no role defines")
    for name in sorted(set(code) - documented):
        fail(readme, f"does not document `{name}` (defined in {code[name]})")


def check_paths(doc):
    text = doc.read_text()
    # Repo-relative paths in backticks: roles/x/y.yml, playbooks/z.yml, docs/a.md
    pattern = r"`((?:roles|playbooks|environments|docs|tests|meta)/[A-Za-z0-9_./*-]+)`"
    for path in sorted(set(re.findall(pattern, text))):
        if "*" in path:
            if not list(ROOT.glob(path)):
                fail(doc, f"names `{path}`, which matches nothing")
        elif not (ROOT / path).exists():
            fail(doc, f"names `{path}`, which does not exist")


def check_links(doc):
    for target in re.findall(r"\]\((?!https?://|#)([^)]+)\)", doc.read_text()):
        target = target.split("#")[0]
        if not target:
            continue
        if not (doc.parent / target).exists():
            fail(doc, f"links to {target}, which does not exist")


def check_playbooks(doc):
    for name in sorted(set(re.findall(r"playbooks/([a-z_]+)\.yml", doc.read_text()))):
        if not (ROOT / "playbooks" / f"{name}.yml").exists():
            fail(doc, f"references playbooks/{name}.yml, which does not exist")


def main():
    code = code_variables()
    check_variable_table(code)
    for doc in DOCS:
        # The changelog is a historical record: it legitimately names paths that
        # a release removed. Its links still have to resolve.
        if doc.name != "CHANGELOG.md":
            check_paths(doc)
            check_playbooks(doc)
        check_links(doc)

    if failures:
        print(f"{len(failures)} documentation mismatch(es):\n")
        for line in failures:
            print(f"  {line}")
        return 1

    print(f"docs match the code: {len(code)} variables, {len(DOCS)} documents checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
