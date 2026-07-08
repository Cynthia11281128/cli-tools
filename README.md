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
| `cli-tools ply-viewer` | Prompt for or accept a `.ply` file, start a lightweight Three.js web viewer, and register it as a named port service. | `cli-tools ply-viewer /path/to/model.ply` |
| `cli-tools port-start` | Start a long-running command in the background, assign it a name and port, and record its PID and log path. | `cli-tools port-start viewer 7860 -- python server.py --port 7860` |
| `cli-tools port-list` | List local named port services, or use `--remote` to list them over SSH with `CLI_TOOLS_SSH_REMOTE` from `.env`. | `cli-tools port-list --remote` |
| `cli-tools port-stop` | Stop one named port service, or every managed service with `--all`. | `cli-tools port-stop --all` |
| `cli-tools port-clear-cache` | Clear named port registry and logs when no managed port services are active. | `cli-tools port-clear-cache` |
| `cli-tools ssh-tunnel` | Open SSH local port forwards for entered ports, or use `--all` to forward every active named remote port. | `cli-tools ssh-tunnel --all` |

## Named Ports

Use named ports for local web services that should be easy to find and stop
later:

```bash
cli-tools port-start viewer 7860 -- python visualize_web/server.py --port 7860
cli-tools port-list
cli-tools port-list --remote
cli-tools port-stop viewer
cli-tools port-stop --all
cli-tools port-clear-cache
```

`port-start` requires `--` before the command it should run. Names may contain
only letters, numbers, `.`, `_`, and `-`. `port-stop --all` stops every active
service in the cli-tools registry. `port-stop` only stops services in the
registry; it does not kill arbitrary processes by port number.
`port-list --remote` runs `cli-tools port-list` on the SSH target configured as
`CLI_TOOLS_SSH_REMOTE` in local `.env`; set `CLI_TOOLS_REMOTE_CLI` there if the
remote `cli-tools` command is not on PATH.

Use `cli-tools ssh-tunnel --all` to fetch active remote named ports, connect all
of them with one SSH tunnel, and print `name -> local URL` lines. While it is
running, enter `s` to sync newly added remote ports or `q` to stop the tunnel.

## PLY Viewer

Start an ordinary mesh or point-cloud PLY viewer on the machine where the file
lives:

```bash
cli-tools ply-viewer
cli-tools ply-viewer /path/to/model.ply
cli-tools ply-viewer /path/to/model.ply --port 8765 --name scene-view
```

When no path is given, `ply-viewer` prompts for one. If no port is given, it
automatically picks a free port, starts the viewer through `port-start`, and
prints the local URL. For remote servers, run this on the server first, then run
the following on your local machine:

```bash
cli-tools ssh-tunnel --all
```

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
