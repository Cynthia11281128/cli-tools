# Agent Guide

This repository is a personal command-line toolbox. Every tool added here
should be installable and directly callable from the shell, just like
`dvc-push-data`.

## Repository Contract

- Put user-facing commands in `bin/`.
- Each file in `bin/` should be a standalone executable command.
- Command names should be stable, lowercase, and hyphen-separated.
- `install.sh` installs commands from `bin/` onto `PATH` using symlinks.
- `README.md` explains how to install the toolbox and how to use each command.
- Avoid project-specific absolute paths unless a command is explicitly
  documented as project-specific.

## Adding a New Tool

When adding a tool, make it usable with this pattern:

```bash
tool-name --help
tool-name [arguments]
```

Checklist:

- Add the executable as `bin/tool-name`.
- Make it executable with `chmod +x bin/tool-name`.
- Support `-h` or `--help`.
- Validate required commands and inputs before doing work.
- Print clear errors to stderr and exit non-zero on failure.
- Keep default behavior conservative and reversible.
- Update `README.md` with install and usage examples.
- Ensure `./install.sh` installs the command without special cases.

## Script Style

Use Bash for small tools unless another runtime clearly improves the result.
Start Bash commands with:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

Prefer small functions for repeated behavior such as `die`, `usage`, and
`require_cmd`. Keep output concise and actionable.

## Installation Rules

- Installation should create symlinks from an install directory to files in
  this repository's `bin/`.
- Prefer a writable directory that is already on `PATH`.
- Honor `TOOLS_INSTALL_DIR` when it is set.
- Do not overwrite an existing command unless it already points to the same
  file in this repository.
- A freshly cloned copy of this repository should work after running:

  ```bash
  ./install.sh
  ```

## Safety Rules

- Do not silently delete, overwrite, reset, merge, rebase, or force-push user
  work.
- If a command mutates files, repositories, remotes, or external services, make
  its preconditions explicit and fail early when the environment is unsafe.
- Keep secrets out of tracked files and command output.
- Do not couple one command's assumptions to unrelated tools in this repo.

## Validation

Before committing changes, run syntax checks for all shell commands:

```bash
bash -n install.sh bin/*
```

For a behavior change, test the affected command in a temporary directory or a
throwaway repository before using it on real work.

## Git Hygiene

- Keep generated caches and temporary files out of Git.
- Commit only intentional changes.
- Respect unrelated local changes in this repository and in any repo where the
  tools are tested.
