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
dvc-pull-data --help
```

## Commands

| Command | Purpose | Typical use |
|---|---|---|
| `dvc-push-data` | Publish current `data/` through DVC and Git metadata. | `cd /path/to/repo && dvc-push-data` |
| `dvc-pull-data` | Pull latest Git data pointer and DVC data. | `cd /path/to/repo && dvc-pull-data` |

Both DVC commands must run inside a Git/DVC repository. They use conservative
safety checks: the working tree must be clean, the branch must have an upstream,
and unsafe Git states are rejected instead of being merged, rebased, stashed, or
force-pushed automatically.

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
