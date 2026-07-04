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
Open a new shell after installing; toolbox command completion is scoped to
`cli-tools <Tab>` so direct tool names do not mix into normal command
completion.

To choose the install location explicitly:

```bash
TOOLS_INSTALL_DIR=/path/to/bin ./install.sh
```

After renaming or removing commands, reinstall from scratch:

```bash
./install.sh --reinstall
```

Verify installation:

```bash
cli-tools --help
```

## Commands

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools` | List or run toolbox commands with scoped subcommand completion. | `cli-tools list` |
| `dvc-push-data` | Review `data/` changes, confirm, then run DVC push and Git metadata commit/push. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && dvc-push-data` |
| `dvc-pull-data` | Pull latest Git data pointer and DVC data. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && dvc-pull-data` |
| `git-quick-push` | Review modified/deleted/untracked files, confirm, then commit and push. Stops on unsafe Git states. | `cd /path/to/repo && git-quick-push` |
| `list` | List executable commands available in this toolbox. | `list` |
| `notify-done` | Run a command and send a desktop notification when it finishes. Returns the wrapped command's exit code. | `notify-done -- make test` |

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
