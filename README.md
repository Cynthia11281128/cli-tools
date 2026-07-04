# cli-tools

Personal command-line tools exposed through one `cli-tools` shell entrypoint.

## Install

Clone the repository, then run:

```bash
git clone https://github.com/Cynthia11281128/cli-tools.git ~/cli-tools
cd ~/cli-tools
./install.sh
```

`install.sh` installs only the `cli-tools` entrypoint into a writable directory
on `PATH` using a symlink. Run toolbox commands as `cli-tools <command>`.
Open a new shell after installing; `cli-tools <Tab>` completes toolbox
subcommands without mixing direct tool names into normal command completion.

To choose the install location explicitly:

```bash
TOOLS_INSTALL_DIR=/path/to/bin ./install.sh
```

To refresh the entrypoint and completion symlinks:

```bash
./install.sh --reinstall
```

Verify installation:

```bash
./install.sh --check
```

## Commands

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools` | List or run toolbox commands with scoped subcommand completion. | `cli-tools list` |
| `cli-tools dvc-push-data` | Review `data/` changes, confirm, then run DVC push and Git metadata commit/push. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && cli-tools dvc-push-data` |
| `cli-tools dvc-pull-data` | Pull latest Git data pointer and DVC data. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && cli-tools dvc-pull-data` |
| `cli-tools git-quick-push` | Review modified/deleted/untracked files, confirm, then commit and push. Stops on unsafe Git states. | `cd /path/to/repo && cli-tools git-quick-push` |
| `cli-tools list` | List executable subcommands available in this toolbox. | `cli-tools list` |
| `cli-tools notify-done` | Run a command and send a desktop notification when it finishes. Returns the wrapped command's exit code. | `cli-tools notify-done -- make test` |

## Adding Tools

Add new commands as executable files in `bin/`:

```bash
bin/my-tool --help
chmod +x bin/my-tool
./install.sh
cli-tools my-tool --help
```

Guidelines:

- Use lowercase, hyphen-separated command names.
- Support `-h` or `--help`.
- Validate required commands and inputs before mutating anything.
- Print clear errors and exit non-zero on failure.
- Document the command in this README.
