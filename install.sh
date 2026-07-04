#!/usr/bin/env bash
set -euo pipefail

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

path_contains() {
  case ":$PATH:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source_cmd="$script_dir/bin/dvc-push-data"

[[ -f "$source_cmd" ]] || die "missing command: $source_cmd"
chmod +x "$source_cmd"

if [[ -n "${TOOLS_INSTALL_DIR:-}" ]]; then
  install_dir="$TOOLS_INSTALL_DIR"
elif [[ -d "$HOME/.local/bin" && -w "$HOME/.local/bin" ]] && path_contains "$HOME/.local/bin"; then
  install_dir="$HOME/.local/bin"
elif [[ -n "${CONDA_PREFIX:-}" && -d "$CONDA_PREFIX/bin" && -w "$CONDA_PREFIX/bin" ]] && path_contains "$CONDA_PREFIX/bin"; then
  install_dir="$CONDA_PREFIX/bin"
elif [[ -d "$HOME/miniconda3/bin" && -w "$HOME/miniconda3/bin" ]] && path_contains "$HOME/miniconda3/bin"; then
  install_dir="$HOME/miniconda3/bin"
else
  install_dir="$HOME/.local/bin"
fi

mkdir -p "$install_dir"
[[ -w "$install_dir" ]] || die "install directory is not writable: $install_dir"

target="$install_dir/dvc-push-data"

if [[ -e "$target" || -L "$target" ]]; then
  existing="$(readlink "$target" 2>/dev/null || true)"
  if [[ "$existing" != "$source_cmd" ]]; then
    die "refusing to overwrite existing command: $target"
  fi
fi

ln -sfn "$source_cmd" "$target"

printf 'Installed: %s -> %s\n' "$target" "$source_cmd"
if ! path_contains "$install_dir"; then
  printf 'Warning: %s is not in PATH. Add it to your shell startup file.\n' "$install_dir" >&2
fi
