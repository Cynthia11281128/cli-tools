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

## Update

For normal updates, pull the latest repository contents:

```bash
cd ~/cli-tools
git pull
cli-tools list
```

Because `cli-tools` dispatches commands from this repository's `bin/` directory,
changes to existing tools and newly added executable subcommands usually work
after `git pull`.

Run `./install.sh` again only after the first clone, when the `cli-tools`
command is missing or broken, when changing install directories, or when
refreshing shell completion:

```bash
./install.sh --reinstall
```

## Commands

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools` | List or run toolbox commands with scoped subcommand completion. | `cli-tools list` |
| `cli-tools dvc-clear-cache` | Preview and confirm local DVC cache cleanup for the current workspace. Never clears DVC remote storage. | `cd /path/to/repo && cli-tools dvc-clear-cache` |
| `cli-tools dvc-push-data` | Review a concise `data/` change summary and changed folders, confirm, then run DVC push and Git metadata commit/push. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && cli-tools dvc-push-data` |
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
