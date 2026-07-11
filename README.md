# cli-tools

Small Bash command-line toolbox exposed through one `cli-tools` entrypoint.

The installer only adds one command to `PATH`: `cli-tools`. All other tools are
run as subcommands, for example `cli-tools git-quick-push` or
`cli-tools port-list`, which keeps shell completion and command names scoped to
this toolbox.

Most commands are intentionally conservative. Git and DVC tools show what they
will change and ask for confirmation before committing or pushing. Port tools
only manage services that were registered by this toolbox.

## Quick Start

```bash
git clone https://github.com/Cynthia11281128/cli-tools.git ~/cli-tools
cd ~/cli-tools
./install.sh
./install.sh --check
cli-tools list
```

Open a new shell after installing to enable `cli-tools <Tab>` completion.

Some commands use local configuration from `.env`. Copy the example when you
need SSH or Codex-related tools:

```bash
cp .env.example .env
```

Edit `.env` for your machine. The real `.env` file is ignored by Git and should
not be committed.

## Requirements

Core requirements:

- Bash
- Git

Command-specific requirements:

- `dvc` for DVC commands
- `ssh` for remote port listing and tunnels
- `npx` for Codex commands
- `python3` for GLB, image, and PLY viewers
- `notify-send` for desktop notifications

## Install

```bash
./install.sh
./install.sh --check
```

`./install.sh` chooses a writable install directory that is already on `PATH`
when possible. To choose the install directory explicitly:

```bash
TOOLS_INSTALL_DIR=/path/to/bin ./install.sh
```

Use `--reinstall` to recreate the `cli-tools` symlink and shell completion
symlink for this checkout:

```bash
./install.sh --reinstall
```

`--reinstall` only manages the current namespace-only install target. It does
not delete older direct command symlinks such as `git-quick-push` or `list`.

## Update

```bash
cd ~/cli-tools
git pull
./install.sh --check
```

Normal updates only need `git pull` because `cli-tools` dispatches commands
from this checkout. Re-run `./install.sh --reinstall` if the entrypoint or shell
completion is missing or broken.

## Configuration

Create local configuration from the tracked example:

```bash
cp .env.example .env
```

Available keys:

| Key | Used by | Purpose |
|---|---|---|
| `CLI_TOOLS_SSH_REMOTE` | `port-list --remote`, `ssh-tunnel` | SSH target such as `user@example.com`. |
| `CLI_TOOLS_REMOTE_CLI` | `port-list --remote`, `ssh-tunnel --all` | Optional remote path to `cli-tools` when it is not on remote `PATH`. |
| `CODEX_ADD_ROOT` | `codex-add` | Initial directory for interactive project path completion. |
| `CODEX_WEB_PASSWORD` | `codex-web` | Password passed to `codexapp`; keep this private. |

## Commands

### Codex

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools codex-add` | Open an existing codexapp project folder. Supports path arguments and interactive directory Tab completion from `CODEX_ADD_ROOT`. | `cli-tools codex-add /path/to/project` |
| `cli-tools codex-web` | Start codexapp as a named port service. Requires `CODEX_WEB_PASSWORD` in local `.env`; pass `--path` and `--port` for your project. | `cli-tools codex-web --path /path/to/project --port 5900` |

### DVC

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools dvc-clear-cache` | Preview and confirm local DVC cache cleanup for the current workspace. Never clears DVC remote storage. | `cd /path/to/repo && cli-tools dvc-clear-cache` |
| `cli-tools dvc-push-data` | Review a concise `data/` change summary and changed folders, confirm, then run DVC push and Git metadata commit/push. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && cli-tools dvc-push-data` |
| `cli-tools dvc-pull-data` | Pull latest Git data pointer and DVC data. Requires a clean Git/DVC repo with upstream. | `cd /path/to/repo && cli-tools dvc-pull-data` |

### Viewer

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools glb-viewer` | Start a lightweight Three.js viewer for a `.glb` file and register it as a named port service. | `cli-tools glb-viewer /path/to/model.glb` |
| `cli-tools img-viewer` | Start a lightweight web viewer for one image or a folder of images and register it as a named port service. | `cli-tools img-viewer /path/to/images` |
| `cli-tools ply-viewer` | Start a lightweight Three.js viewer for a `.ply` file or PLY sequence directory and register it as a named port service. | `cli-tools ply-viewer --sequence /path/to/optimization_snapshots` |

### Port

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools port-start` | Start a long-running command in the background, assign it a name and port, and record its PID and log path. | `cli-tools port-start viewer 7860 -- python server.py --port 7860` |
| `cli-tools port-list` | List local named port services, or use `--remote` to list services over SSH. | `cli-tools port-list --full` |
| `cli-tools port-stop` | Stop one or more managed services by name or port, or every managed service with `--all`. | `cli-tools port-stop viewer 7860` |
| `cli-tools port-clear-cache` | Clear named port registry and logs when no managed port services are active. | `cli-tools port-clear-cache` |
| `cli-tools ssh-tunnel` | Open SSH local port forwards for entered ports, or use `--all` to forward every active named remote port. | `cli-tools ssh-tunnel --all` |

### Other

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools` | List or run toolbox commands with scoped subcommand completion. | `cli-tools list` |
| `cli-tools git-quick-push` | Review modified/deleted/untracked files, confirm, then commit and push. Stops on unsafe Git states. | `cd /path/to/repo && cli-tools git-quick-push` |
| `cli-tools list` | List executable subcommands available in this toolbox. | `cli-tools list` |
| `cli-tools notify-done` | Run a command and send a desktop notification when it finishes. Returns the wrapped command's exit code. | `cli-tools notify-done -- make test` |

## Git and DVC Safety

`git-quick-push`, `dvc-push-data`, and `dvc-pull-data` must run inside a Git
repository on a branch with an upstream. They reject detached HEAD, merge,
rebase, cherry-pick, and diverged or behind-upstream states instead of trying to
repair them automatically.

`git-quick-push` shows the branch, upstream, and all modified, deleted, and
untracked files before asking for confirmation and a commit message.

`dvc-push-data` shows DVC data changes before running `dvc add data`,
`dvc push`, Git commit, and Git push.

## Named Ports

Use named ports for local web services that should be easy to find and stop
later:

```bash
cli-tools port-start viewer 7860 -- python server.py --port 7860
cli-tools port-list
cli-tools port-list --full
cli-tools port-stop viewer
cli-tools port-stop 7860
cli-tools port-stop --all
cli-tools port-clear-cache
```

`port-start` requires `--` before the command it should run. Names may contain
only letters, numbers, `.`, `_`, and `-`. `port-stop` only stops services in the
cli-tools registry; it does not kill arbitrary unregistered processes by port
number. `port-list` output is sorted by service name.

Remote port discovery uses `CLI_TOOLS_SSH_REMOTE` from `.env`:

```bash
cli-tools port-list --remote
cli-tools port-list --remote --full
```

Use `ssh-tunnel --all` to fetch active remote named ports, forward them through
one SSH connection, and print `name -> local URL` lines sorted by name:

```bash
cli-tools ssh-tunnel --all
```

While it is running, enter `s` to refresh remote ports and reprint the full URL
list, or `q` to stop the tunnel.

## Codex Tools

Open an existing codexapp project folder:

```bash
cli-tools codex-add /path/to/project
cli-tools codex-add
```

When no path is provided, `codex-add` prompts for a project folder with
directory Tab completion starting from `CODEX_ADD_ROOT` in local `.env`.

Start codexapp as a named port service:

```bash
cli-tools codex-web --path /path/to/project --port 5900
```

`codex-web` prompts for a project path and port if they are not provided. Store
the password in local `.env` as `CODEX_WEB_PASSWORD`; it is not tracked by Git.

## Viewers

Start a single-file binary glTF viewer on the machine where the file lives:

```bash
cli-tools glb-viewer /path/to/model.glb
cli-tools glb-viewer /path/to/model.glb --port 8765 --name scene-view
```

Start an ordinary mesh or point-cloud PLY viewer:

```bash
cli-tools ply-viewer /path/to/model.ply
cli-tools ply-viewer --sequence /path/to/optimization_snapshots
cli-tools ply-viewer /path/to/model.ply --port 8765 --name scene-view
```

Start a single-image or image-folder viewer:

```bash
cli-tools img-viewer /path/to/image.png
cli-tools img-viewer /path/to/images
cli-tools img-viewer /path/to/images --port 8765 --name image-review
```

Folder mode reads supported images from the top-level directory, shows a left
side list for direct selection, and supports left/right arrow key navigation.
Supported formats are `jpg`, `jpeg`, `png`, `webp`, `gif`, and `svg`.

All viewers register themselves through `port-start`, print the local URL, and
show the service name in the browser tab and viewer title. For remote servers,
start the viewer on the server first, then run this locally:

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

Before committing shell changes, run:

```bash
bash -n install.sh bin/* completions/* lib/*.bash
```
