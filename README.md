# cli-tools

`cli-tools` is a small command-line toolbox exposed through one entrypoint:
`cli-tools`.

All tools run as subcommands, such as `cli-tools port-list` or
`cli-tools git-quick-push`. Linux / WSL gets the full Bash toolbox. Windows
PowerShell gets a native Windows implementation for the port-management subset.

## Contents

- [Installation](#installation)
- [Update](#update)
- [Basic Usage](#basic-usage)
- [Commands](#commands)
- [Configuration](#configuration)
- [Adding Commands](#adding-commands)
- [Notes](#notes)

## Installation

### Linux / WSL

```bash
git clone https://github.com/Cynthia11281128/cli-tools.git ~/cli-tools
cd ~/cli-tools
./install.sh
./install.sh --check
cli-tools list
```

Open a new shell after installing to enable `cli-tools <Tab>` completion.

If `cli-tools` is not found, add the user-local bin directory to `PATH`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

To recreate the entrypoint and completion links:

```bash
./install.sh --reinstall
```

### Windows PowerShell

```powershell
git clone https://github.com/Cynthia11281128/cli-tools.git $HOME\cli-tools
cd $HOME\cli-tools
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-windows.ps1
cli-tools list
```

If `cli-tools` is not found immediately after installation, close and reopen
PowerShell so the updated user `PATH` is loaded.

## Update

### Linux / WSL

```bash
cd ~/cli-tools
git pull
./install.sh --check
```

Re-run `./install.sh --reinstall` if the entrypoint or shell completion is
missing or broken.

### Windows PowerShell

```powershell
cd $HOME\cli-tools
git pull
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-windows.ps1
cli-tools list
```

Windows users should re-run the installer after pulling updates because the
native entrypoint is copied into the user executable directory.

## Basic Usage

```bash
cli-tools list
cli-tools <command> --help
cli-tools port-list --full
```

Start, inspect, and stop a named local service:

```bash
cli-tools port-start demo 8765 -- python server.py --port 8765
cli-tools port-list --full
cli-tools port-stop demo
```

Windows example:

```powershell
cli-tools port-start demo 8765 -- python -m http.server 8765 --bind 127.0.0.1
cli-tools port-list --full
cli-tools port-stop demo
```

## Commands

### Port

| Command | Platform | Purpose |
|---|---|---|
| `port-start` | Linux / Windows | Start a long-running command, assign it a name and port, and record its PID and log path. |
| `port-list` | Linux / Windows | List managed named port services. |
| `port-stop` | Linux / Windows | Stop one or more managed services. |
| `port-restart` | Linux / Windows | Restart one or more managed services. |
| `port-rename` | Linux / Windows | Rename a managed service without restarting it. |
| `port-clear-cache` | Linux / Windows | Clear the port registry and logs when no managed services are active. |
| `ssh-tunnel` | Linux | Create SSH local port forwards, including forwarding all active remote named ports. |

### Git / DVC

| Command | Platform | Purpose |
|---|---|---|
| `git-quick-push` | Linux | Review local Git changes, confirm, then commit and push. |
| `dvc-push-data` | Linux | Review data changes, push DVC data, then commit and push Git metadata. |
| `dvc-pull-data` | Linux | Pull the latest Git data pointer and DVC data. |
| `dvc-clear-cache` | Linux | Preview and clean local DVC cache without touching remote storage. |

### Codex

| Command | Platform | Purpose |
|---|---|---|
| `codex-add` | Linux | Open an existing project folder with `codexapp`. |
| `codex-web` | Linux | Start `codexapp` as a managed named port service. |

### Viewers

| Command | Platform | Purpose |
|---|---|---|
| `viewer-img` | Linux | View one image or an image folder in a browser. |
| `viewer-img-compare` | Linux | Compare two image folders side by side. |
| `viewer-ply` | Linux | View PLY files, PLY folders, or PLY sequences. |
| `viewer-ply-add` | Linux | Add a PLY file to a running ordinary `viewer-ply` page. |
| `viewer-glb` | Linux | View a GLB model in a browser. |
| `viewer-video` | Linux | View MP4 or MOV video files in a browser. |
| `cloud-loader` | Linux | Browse server-side folders and load PLY files into a browser viewer. |

Compatibility aliases such as `img-viewer`, `ply-viewer`, `glb-viewer`, and
`video-viewer` may exist, but new usage should prefer the `viewer-*` commands.

### Ageaf / Other

| Command | Platform | Purpose |
|---|---|---|
| `ageaf-start` | Linux | Start the Ageaf watcher and host as one managed service. |
| `ageaf-stop` | Linux | Stop the Ageaf service started by `ageaf-start`. |
| `notify-done` | Linux | Run a command and send a desktop notification when it finishes. |
| `list` | Linux / Windows | List available `cli-tools` subcommands. |

## Configuration

Some commands read local settings from `.env`. Copy the example when needed:

```bash
cp .env.example .env
```

Common keys:

| Key | Purpose |
|---|---|
| `CLI_TOOLS_SSH_REMOTE` | SSH target for remote port listing and tunnels. |
| `CLI_TOOLS_REMOTE_CLI` | Remote `cli-tools` path when it is not on the remote `PATH`. |
| `CODEX_ADD_ROOT` | Default project root for interactive `codex-add`. |
| `CODEX_WEB_PASSWORD` | Password passed to `codex-web`; keep it private. |

## Adding Commands

New commands are not automatically cross-platform.

### Linux / WSL

Add an executable script under `bin/`:

```bash
bin/my-command
chmod +x bin/my-command
cli-tools list
cli-tools my-command --help
```

Use this path for Bash-based tools. Put reusable code or assets under `lib/`.
Document private local settings in `.env.example`.

### Windows PowerShell

Windows native commands must be added to:

```text
windows/cli-tools-native.ps1
```

After editing, reinstall the Windows entrypoint:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-windows.ps1
cli-tools list
```

### Cross-platform commands

To make a command work on both Linux / WSL and Windows:

1. Put shared implementation in `lib/` when practical, for example Python or Node.
2. Add a Linux wrapper in `bin/my-command`.
3. Add a Windows dispatcher entry in `windows/cli-tools-native.ps1`.
4. Mark the command as `Linux / Windows` in the command table.

## Notes

- `port-start` requires `--` before the command it should run.
- Windows native support is currently limited to `list` and `port-*`.
- Git and DVC commands ask for confirmation before committing, pushing, or
  cleaning data.
- Run `cli-tools <command> --help` for command-specific options.
