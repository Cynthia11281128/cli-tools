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

- `npm` for Ageaf commands
- `dvc` for DVC commands
- `ssh` for remote port listing and tunnels
- `npx` for Codex commands
- `python3` for GLB, image, PLY, and cloud-loader viewers
- `python3` for video viewing; optional `cv2` for video metadata and frame previews
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

### Ageaf

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools ageaf-start` | Start Ageaf's extension watcher and local host as one managed background service. Defaults to `~/Ageaf` on port `3210`. | `cli-tools ageaf-start` |
| `cli-tools ageaf-stop` | Stop the Ageaf service started by `ageaf-start`. | `cli-tools ageaf-stop` |
| `cli-tools port-list --full` | Check Ageaf service status, PID, command, and log path. | `cli-tools port-list --full` |

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
| `cli-tools cloud-loader` | Start a server-side PLY browser; import `.ply` files or the current folder from the machine running the service and toggle each cloud in a side panel. | `cli-tools cloud-loader` |
| `cli-tools viewer-glb` | Start a lightweight Three.js viewer for a `.glb` file and register it as a named port service. | `cli-tools viewer-glb /path/to/model.glb` |
| `cli-tools viewer-img` | Start a lightweight web viewer for one image or a folder of images and register it as a named port service. | `cli-tools viewer-img /path/to/images` |
| `cli-tools viewer-img-compare` | Start a side-by-side web viewer for two image folders, with independent left and right selectors. | `cli-tools viewer-img-compare /path/to/left /path/to/right` |
| `cli-tools viewer-ply` | Start a lightweight Three.js viewer for a `.ply` file, ordinary PLY folder, or PLY sequence directory and register it as a named port service. | `cli-tools viewer-ply /path/to/a.ply --port 8765` |
| `cli-tools viewer-ply-add` | Add another `.ply` file to an already running ordinary `viewer-ply` page by port. Folder and sequence viewers are not supported. | `cli-tools viewer-ply-add /path/to/b.ply 8765` |
| `cli-tools viewer-video` | Start a lightweight web viewer for a `.mp4` or `.mov` video and register it as a named port service. | `cli-tools viewer-video /path/to/video.MOV` |

### Port

| Command | Purpose | Typical use |
|---|---|---|
| `cli-tools port-start` | Start a long-running command in the background, assign it a name and port, and record its PID and log path. | `cli-tools port-start -- python server.py --port {PORT}` |
| `cli-tools port-list` | List local named port services, or use `--remote` to list services over SSH. | `cli-tools port-list --full` |
| `cli-tools port-rename` | Rename a managed service interactively, or by name/port without restarting it. | `cli-tools port-rename` |
| `cli-tools port-restart` | Restart one or more running managed services interactively, or by name/port. | `cli-tools port-restart` |
| `cli-tools port-stop` | Stop a managed service interactively, by name/port, or every managed service with `--all`. | `cli-tools port-stop` |
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
cli-tools port-start -- python server.py --port {PORT}
cli-tools port-start --env grip -- env PYTHONPATH=src python server.py --port {PORT}
cli-tools port-start viewer -- python server.py --port {PORT}
cli-tools port-start viewer --env grip -- env PYTHONPATH=src python server.py --port {PORT}
cli-tools port-start viewer 7860 -- python server.py --port 7860
cli-tools port-list
cli-tools port-list --full
cli-tools port-rename
cli-tools port-rename viewer demo-viewer
cli-tools port-rename 7860 viewer
cli-tools port-restart
cli-tools port-restart viewer
cli-tools port-restart viewer 7860
cli-tools port-stop
cli-tools port-stop viewer
cli-tools port-stop 7860
cli-tools port-stop --all
cli-tools port-clear-cache
```

`port-start` requires `--` before the command it should run. If the service name
is omitted in an interactive terminal, it asks for one. If the port is omitted
or set to `auto`, it picks the first unused port from `8000`. Use `{PORT}` in
command arguments, or read the selected value from the `PORT` environment
variable. In an interactive terminal, auto-port mode asks which conda
environment to use and lists available envs; choose `0` to run in the current
shell. Use `--name <name>` to force a service name, `--env <name>` to force an
environment, `--no-env` to skip environment selection, or `--ask-env` to prompt
even when passing an explicit port. Passing an explicit positional name and
numeric port keeps the old behavior.

Names may contain only letters, numbers, `.`, `_`, and `-`. `port-rename`
updates only the cli-tools registry name; it does not restart the service, move
its log file, or rewrite the recorded launch command. Run `port-rename` without
arguments to choose an existing service from an interactive list. Run
`port-stop` without arguments to choose one or more services from the same kind
of list. `port-restart` uses the recorded command and the running process'
current working directory, so it only restarts services that are still running.
`port-stop` only stops services in the cli-tools registry; it does not kill
arbitrary unregistered processes by port number. `port-list` output is sorted by
service name.

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

## Ageaf Tools

Ageaf repository: [OniReimu/Ageaf](https://github.com/OniReimu/Ageaf).

Start Ageaf for Overleaf:

```bash
cli-tools ageaf-start
```

The command starts `npm run watch` in `~/Ageaf` and
`HOST=127.0.0.1 PORT=3210 npm run dev` in `~/Ageaf/host` as one managed
background service named `ageaf`.

Use a custom checkout, port, or service name when needed:

```bash
cli-tools ageaf-start --path ~/Ageaf --port 3210 --name ageaf
```

Check status and logs:

```bash
cli-tools port-list --full
```

Stop Ageaf:

```bash
cli-tools ageaf-stop
```

The first time you use Ageaf, load the Chrome extension from
`/home/cynthia/Ageaf/build` in `chrome://extensions`. After that, start Ageaf
with `cli-tools ageaf-start` and refresh the Overleaf project page.

## Viewers

Start a browser video viewer for MP4 or MOV files:

```bash
cli-tools viewer-video /path/to/video.MOV
```

Pass a Python interpreter with OpenCV installed to show video metadata and
enable frame preview fallback for codecs the browser cannot decode directly:

```bash
cli-tools viewer-video /home/xinyuan/VGGT-Long/VGGT-Long-Customized-Dataset/RawVideo/IMG_4642-stairs-wide-60hz.MOV \
  --name stairs-video \
  --python /tmp/tmp_data/miniconda3/envs/vggt/bin/python
```

For HEVC MOV files, browser playback may be unavailable on some systems; the
viewer automatically exposes OpenCV frame playback when `cv2` is available.
The fallback requests every source frame by default, so high-fps HEVC videos can
use substantial CPU and network bandwidth.

Start a single-file binary glTF viewer on the machine where the file lives:

```bash
cli-tools viewer-glb /path/to/model.glb
cli-tools viewer-glb /path/to/model.glb --port 8765 --name scene-view
```

Start an ordinary mesh or point-cloud PLY viewer:

```bash
cli-tools viewer-ply /path/to/model.ply
cli-tools viewer-ply /path/to/ply-folder
cli-tools viewer-ply --sequence /path/to/optimization_snapshots
cli-tools viewer-ply /path/to/model.ply --port 8765 --name scene-view
```

Ordinary PLY folder mode reads top-level `.ply` files, shows a left side list
for direct selection, supports top-level `.ply` symlinks, and supports
left/right arrow key navigation.
`--sequence` is reserved for PlanarSplatting snapshot timelines.

Start a cloud loader when you want to browse and add PLY files from the machine
running the service:

```bash
cli-tools cloud-loader
cli-tools cloud-loader --start-dir /tmp/tmp_data
cli-tools cloud-loader --port 8765 --name cloud-review
```

By default, the server-side picker starts from `/home/xinyuan/GRIP-Layout`.
Pass `--start-dir` to override that for a specific launch.

Use `Browse` to open a server-side picker modal. Click a directory name to
enter it, click `Select` next to a PLY to load one file, or click
`Add Current Folder` to import only direct child `.ply` files from the current
server directory. The loaded-file side panel lets you toggle visibility
independently. The picker modal and loaded-file side panel both include a
case-insensitive text filter for matching names or paths.
Set `Downsample` to `N` before loading to display only every Nth vertex as a
point cloud. Use `Reload Visible` to re-load visible files with a changed
downsample value.
Folders imported with `Add Current Folder` or `Load Path` appear as collapsible
groups in the loaded-file side panel. Use the group checkbox to toggle all PLY
files from that folder at once, or expand the group to control files
individually. Use `Remove` on a group header to unload the whole folder import,
or `Remove` on a file row to unload one PLY without clearing the rest of the
scene.

Start a single-image or image-folder viewer:

```bash
cli-tools viewer-img /path/to/image.png
cli-tools viewer-img /path/to/images
cli-tools viewer-img /path/to/images --port 8765 --name image-review
cli-tools viewer-img /path/to/images --sample-every 5
```

Folder mode reads supported images and top-level image symlinks from the
directory, shows a left side list for direct selection, and supports left/right
arrow key navigation.
Use `--sample-every N` to keep every Nth image after natural sorting.
Supported formats are `jpg`, `jpeg`, `png`, `webp`, `gif`, and `svg`.

Compare two image folders side by side:

```bash
cli-tools viewer-img-compare /path/to/pred /path/to/gt
cli-tools viewer-img-compare /path/to/a /path/to/b --port 8765 --name img-compare
```

Image compare mode reads supported images from the top level of each folder.
The left and right panels switch independently: use the list buttons, `A`/`D`
for the left side, and left/right arrow keys for the right side.

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
