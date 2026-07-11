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
| `cli-tools codex-add` | Open an existing codexapp project folder. Supports path arguments and interactive directory Tab completion from `CODEX_ADD_ROOT`. | `cli-tools codex-add /path/to/project` |
| `cli-tools codex-web` | Prompt for a project path and port, then start codexapp through `port-start`. Requires `CODEX_WEB_PASSWORD` in local `.env`. | `cli-tools codex-web` |
| `cli-tools dvc-clear-cache` | Preview and confirm local DVC cache cleanup for the current workspace. Never clears DVC remote storage. | `cd /path/to/repo && cli-tools dvc-clear-cache` |
| `cli-tools dvc-push-data` | Review a concise `data/` change summary and changed folders, confirm, then run DVC push and Git metadata commit/push. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && cli-tools dvc-push-data` |
| `cli-tools dvc-pull-data` | Pull latest Git data pointer and DVC data. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && cli-tools dvc-pull-data` |
| `cli-tools git-quick-push` | Review modified/deleted/untracked files, confirm, then commit and push. Stops on unsafe Git states. | `cd /path/to/repo && cli-tools git-quick-push` |
| `cli-tools glb-viewer` | Prompt for or accept a `.glb` file, start a lightweight Three.js web viewer, and register it as a named port service. | `cli-tools glb-viewer /path/to/model.glb` |
| `cli-tools list` | List executable subcommands available in this toolbox. | `cli-tools list` |
| `cli-tools notify-done` | Run a command and send a desktop notification when it finishes. Returns the wrapped command's exit code. | `cli-tools notify-done -- make test` |
| `cli-tools ply-viewer` | Prompt for or accept a `.ply` file, or load a PLY sequence directory, start a lightweight Three.js web viewer, and register it as a named port service. | `cli-tools ply-viewer --sequence /path/to/optimization_snapshots` |
| `cli-tools port-start` | Start a long-running command in the background, assign it a name and port, and record its PID and log path. | `cli-tools port-start viewer 7860 -- python server.py --port 7860` |
| `cli-tools port-list` | List local named port services, or use `--full` for status, PID, log, and command details. Supports `--remote` over SSH with `CLI_TOOLS_SSH_REMOTE` from `.env`. | `cli-tools port-list --full` |
| `cli-tools port-stop` | Stop one or more managed services by name or port, or every managed service with `--all`. | `cli-tools port-stop viewer 7860` |
| `cli-tools port-clear-cache` | Clear named port registry and logs when no managed port services are active. | `cli-tools port-clear-cache` |
| `cli-tools ssh-tunnel` | Open SSH local port forwards for entered ports, or use `--all` to forward every active named remote port. | `cli-tools ssh-tunnel --all` |

## Named Ports

Use named ports for local web services that should be easy to find and stop
later:

```bash
cli-tools port-start viewer 7860 -- python visualize_web/server.py --port 7860
cli-tools port-list
cli-tools port-list --full
cli-tools port-list --remote
cli-tools port-stop viewer
cli-tools port-stop 7860
cli-tools port-stop viewer 6006
cli-tools port-stop --all
cli-tools port-clear-cache
```

`port-start` requires `--` before the command it should run. Names may contain
only letters, numbers, `.`, `_`, and `-`. `port-stop --all` stops every active
service in the cli-tools registry. `port-stop` accepts one or more service names
or managed port numbers. It only stops services in the registry; it does not
kill arbitrary unregistered processes by port number.
`port-list` shows `name`, `port`, and `started` by default; use
`port-list --full` to also show status, PID, log path, and command.
`port-list --remote` runs `cli-tools port-list` on the SSH target configured as
`CLI_TOOLS_SSH_REMOTE` in local `.env`; combine it with `--full` for the full
remote table. Set `CLI_TOOLS_REMOTE_CLI` if the remote `cli-tools` command is
not on PATH.

Use `cli-tools ssh-tunnel --all` to fetch active remote named ports, connect all
of them with one SSH tunnel, and print `name -> local URL` lines sorted by name.
While it is running, enter `s` to sync newly added remote ports and reprint the
full URL list, or `q` to stop the tunnel.

## Codex Add

Open an existing codexapp project folder:

```bash
cli-tools codex-add /path/to/project
cli-tools codex-add
```

When no path is provided, the command prompts for a project folder with
directory Tab completion starting from `CODEX_ADD_ROOT` in local `.env`, for
example `CODEX_ADD_ROOT=/path/to/root`.

## Codex Web

Start codexapp as a named port service:

```bash
cli-tools codex-web
```

The command prompts for a project path and port. Press Enter to use
`/home/xinyuan/GRIP-Layout` and port `5900`. Store the password in local `.env`
as `CODEX_WEB_PASSWORD`; it is not tracked by Git.

## GLB Viewer

Start a single-file binary glTF viewer on the machine where the file lives:

```bash
cli-tools glb-viewer
cli-tools glb-viewer /path/to/model.glb
cli-tools glb-viewer /path/to/model.glb --port 8765 --name scene-view
```

When no path is given, `glb-viewer` prompts for the GLB path and a named port
service name. Press Enter at the name prompt to use `glb-view-<port>`. If no
port is given, it automatically picks a free port, starts the viewer through
`port-start`, prints the local URL, and shows the service name in the browser
tab and viewer title. For remote servers, run this on the server first, then run
the following on your local machine:

```bash
cli-tools ssh-tunnel --all
```

## PLY Viewer

Start an ordinary mesh or point-cloud PLY viewer on the machine where the file
lives:

```bash
cli-tools ply-viewer
cli-tools ply-viewer /path/to/model.ply
cli-tools ply-viewer --sequence /path/to/optimization_snapshots
cli-tools ply-viewer /path/to/model.ply --port 8765 --name scene-view
```

When no path is given, `ply-viewer` prompts for the PLY path and a named port
service name. Press Enter at the name prompt to use `ply-view-<port>`. If no
port is given, it automatically picks a free port, starts the viewer through
`port-start`, prints the local URL, and shows the service name in the browser
tab and viewer title. Use `--sequence` with a PlanarSplatting
`optimization_snapshots` directory or an older `plane_plots` directory to play
intermediate PLY files on a timeline. For remote servers, run this on the server
first, then run the following on your local machine:

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
