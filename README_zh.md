# cli-tools

`cli-tools` 是一组小型命令行工具，通过统一入口 `cli-tools` 使用。

所有工具都作为子命令运行，例如 `cli-tools port-list` 或
`cli-tools git-quick-push`。Linux / WSL 使用完整 Bash 工具集。Windows
PowerShell 使用原生 Windows 实现，目前支持端口管理相关子集。

## 目录

- [安装](#安装)
- [更新](#更新)
- [基本用法](#基本用法)
- [工具列表](#工具列表)
- [配置](#配置)
- [添加新命令](#添加新命令)
- [注意事项](#注意事项)

## 安装

### Linux / WSL

```bash
git clone https://github.com/Cynthia11281128/cli-tools.git ~/cli-tools
cd ~/cli-tools
./install.sh
./install.sh --check
cli-tools list
```

安装后打开一个新的 shell，可以启用 `cli-tools <Tab>` 补全。

如果找不到 `cli-tools`，把用户本地 bin 目录加入 `PATH`：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

如果需要重建入口和补全链接：

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

如果安装后立刻找不到 `cli-tools`，关闭并重新打开 PowerShell，让新的用户
`PATH` 生效。

## 更新

### Linux / WSL

```bash
cd ~/cli-tools
git pull
./install.sh --check
```

如果入口或 shell 补全缺失或损坏，再运行 `./install.sh --reinstall`。

### Windows PowerShell

```powershell
cd $HOME\cli-tools
git pull
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-windows.ps1
cli-tools list
```

Windows 用户更新后建议重新运行安装器，因为原生入口会被复制到用户可执行目录。

## 基本用法

```bash
cli-tools list
cli-tools <command> --help
cli-tools port-list --full
```

启动、查看、停止一个命名本地服务：

```bash
cli-tools port-start demo 8765 -- python server.py --port 8765
cli-tools port-list --full
cli-tools port-stop demo
```

Windows 示例：

```powershell
cli-tools port-start demo 8765 -- python -m http.server 8765 --bind 127.0.0.1
cli-tools port-list --full
cli-tools port-stop demo
```

## 工具列表

### Port

| 命令 | 平台 | 用途 |
|---|---|---|
| `port-start` | Linux / Windows | 启动长期运行命令，分配名称和端口，并记录 PID 与日志路径。 |
| `port-list` | Linux / Windows | 列出受管理的命名端口服务。 |
| `port-stop` | Linux / Windows | 停止一个或多个受管理服务。 |
| `port-restart` | Linux / Windows | 重启一个或多个受管理服务。 |
| `port-rename` | Linux / Windows | 不重启服务，只重命名受管理服务。 |
| `port-clear-cache` | Linux / Windows | 在没有活动服务时清理端口 registry 和日志。 |
| `ssh-tunnel` | Linux | 创建 SSH 本地端口转发，也可转发远端所有活动命名端口。 |

### Git / DVC

| 命令 | 平台 | 用途 |
|---|---|---|
| `git-quick-push` | Linux | 查看本地 Git 变更，确认后提交并推送。 |
| `dvc-push-data` | Linux | 查看数据变更，推送 DVC 数据，再提交并推送 Git 元数据。 |
| `dvc-pull-data` | Linux | 拉取最新 Git 数据指针和 DVC 数据。 |
| `dvc-clear-cache` | Linux | 预览并清理本地 DVC cache，不影响远端存储。 |

### Codex

| 命令 | 平台 | 用途 |
|---|---|---|
| `codex-add` | Linux | 用 `codexapp` 打开已有项目目录。 |
| `codex-web` | Linux | 把 `codexapp` 启动为受管理命名端口服务。 |

### Viewers

| 命令 | 平台 | 用途 |
|---|---|---|
| `viewer-img` | Linux | 在浏览器中查看单张图片或图片文件夹。 |
| `viewer-img-compare` | Linux | 左右对比两个图片文件夹。 |
| `viewer-ply` | Linux | 查看 PLY 文件、PLY 文件夹或 PLY 序列。 |
| `viewer-ply-add` | Linux | 向正在运行的普通 `viewer-ply` 页面追加 PLY 文件。 |
| `viewer-glb` | Linux | 在浏览器中查看 GLB 模型。 |
| `viewer-video` | Linux | 在浏览器中查看 MP4 或 MOV 视频。 |
| `cloud-loader` | Linux | 浏览服务端文件夹，并把 PLY 文件加载到浏览器查看器。 |

兼容旧命令的别名可能仍然存在，例如 `img-viewer`、`ply-viewer`、
`glb-viewer`、`video-viewer`；新用法推荐使用 `viewer-*` 命令。

### Ageaf / Other

| 命令 | 平台 | 用途 |
|---|---|---|
| `ageaf-start` | Linux | 把 Ageaf watcher 和 host 作为一个受管理服务启动。 |
| `ageaf-stop` | Linux | 停止由 `ageaf-start` 启动的 Ageaf 服务。 |
| `notify-done` | Linux | 运行命令，并在结束时发送桌面通知。 |
| `list` | Linux / Windows | 列出可用的 `cli-tools` 子命令。 |

## 配置

部分命令会读取本地 `.env` 设置。需要时从示例复制：

```bash
cp .env.example .env
```

常用配置项：

| Key | 用途 |
|---|---|
| `CLI_TOOLS_SSH_REMOTE` | 用于远程端口列表和 tunnel 的 SSH 目标。 |
| `CLI_TOOLS_REMOTE_CLI` | 远端 `PATH` 中没有 `cli-tools` 时，指定远端路径。 |
| `CODEX_ADD_ROOT` | `codex-add` 交互模式的默认项目根目录。 |
| `CODEX_WEB_PASSWORD` | 传给 `codex-web` 的密码，请保持私密。 |

## 添加新命令

新命令不会自动跨平台。

### Linux / WSL

在 `bin/` 下添加可执行脚本：

```bash
bin/my-command
chmod +x bin/my-command
cli-tools list
cli-tools my-command --help
```

Bash 工具走这条路径。可复用代码或资源放在 `lib/`。私有本地配置写进
`.env.example` 作为示例，真实值放在 `.env`。

### Windows PowerShell

Windows 原生命令必须添加到：

```text
windows/cli-tools-native.ps1
```

修改后重新安装 Windows 入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-windows.ps1
cli-tools list
```

### 跨平台命令

如果希望一个命令同时支持 Linux / WSL 和 Windows：

1. 尽量把共享实现放在 `lib/`，例如 Python 或 Node。
2. 在 `bin/my-command` 中添加 Linux wrapper。
3. 在 `windows/cli-tools-native.ps1` 中添加 Windows dispatcher 入口。
4. 在命令表中把平台标记为 `Linux / Windows`。

## 注意事项

- `port-start` 要求在要运行的命令前使用 `--` 分隔。
- Windows 原生版目前只支持 `list` 和 `port-*`。
- Git 和 DVC 命令会在提交、推送或清理数据前请求确认。
- 命令级选项请运行 `cli-tools <command> --help` 查看。
