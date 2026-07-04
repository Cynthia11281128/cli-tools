# tools

Personal command-line tools.

## Install

Run:

```bash
cd /home/cynthia/tools
./install.sh
```

This installs `dvc-push-data` into a writable directory on `PATH`.

To choose the install location explicitly:

```bash
TOOLS_INSTALL_DIR=/path/to/bin ./install.sh
```

## dvc-push-data

Run inside a Git repository that already uses DVC:

```bash
cd /path/to/project
dvc-push-data
```

The command publishes the repository's `data/` directory:

1. `dvc add data`
2. `dvc push`
3. commit `data.dvc` and `.gitignore`
4. `git push`

Safety rules:

- The Git working tree must be clean before the command starts.
- The current branch must have an upstream.
- The current branch must be exactly synced with its upstream.
- The command refuses to commit files other than `data.dvc` and `.gitignore`.
- The Git commit message is requested interactively every time.
