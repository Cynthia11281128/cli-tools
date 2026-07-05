# cli-tools

Personal command-line tools exposed through one `cli-tools` shell entrypoint.

## Install

```bash
git clone https://github.com/Cynthia11281128/cli-tools.git ~/cli-tools
cd ~/cli-tools
./install.sh
./install.sh --check
```

Run tools as `cli-tools <command>`. Open a new shell after installing to enable
completion.

Optional install controls:

```bash
TOOLS_INSTALL_DIR=/path/to/bin ./install.sh
./install.sh --reinstall
```

## Update

```bash
cd ~/cli-tools
git pull
cli-tools list
```

`git pull` is enough for normal updates because `cli-tools` runs commands from
this checkout. Re-run `./install.sh --reinstall` only if the entrypoint or shell
completion is missing or broken.

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
| `cli-tools ssh-tunnel` | Open SSH local port forwards for ports you enter, print local URLs, and use `CLI_TOOLS_SSH_REMOTE` from local `.env`. | `cli-tools ssh-tunnel` |

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
