# cli-tools

Personal command-line tools that can be installed once and called directly from
the shell.

## Install

Clone the repository, then run:

```bash
git clone https://github.com/Cynthia11281128/cli-tools.git ~/cli-tools
cd ~/cli-tools
./install.sh
```

`install.sh` installs every executable command in `bin/` into a writable
directory on `PATH` using symlinks.

To choose the install location explicitly:

```bash
TOOLS_INSTALL_DIR=/path/to/bin ./install.sh
```

Verify installation:

```bash
which dvc-push-data
dvc-push-data --help
```

## Commands

- `dvc-push-data`: publish the current Git/DVC repository's `data/` directory.

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

## Adding Tools

Add new commands as executable files in `bin/`:

```bash
bin/my-tool --help
chmod +x bin/my-tool
./install.sh
```

Guidelines:

- Use lowercase, hyphen-separated command names.
- Support `-h` or `--help`.
- Validate required commands and inputs before mutating anything.
- Print clear errors and exit non-zero on failure.
- Document the command in this README.
