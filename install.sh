#!/usr/bin/env bash
set -euo pipefail

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  ./install.sh
  ./install.sh --reinstall

Install executable commands from bin/ onto PATH using symlinks.

Options:
  --reinstall  Remove existing symlinks in the install directory that point to
               this repository's bin/ directory, then install current commands.
  -h, --help   Show this help.
USAGE
}

path_contains() {
  case ":$PATH:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

path_starts_with() {
  case "$1" in
    "$2"/*) return 0 ;;
    *) return 1 ;;
  esac
}

configure_completion_startup() {
  local completion_target="$1"
  local startup_file="${CLI_TOOLS_COMPLETION_STARTUP_FILE:-}"
  local marker_start="# >>> cli-tools completion >>>"
  local marker_end="# <<< cli-tools completion <<<"

  if [[ "${CLI_TOOLS_SKIP_COMPLETION_STARTUP:-}" == "1" ]]; then
    return 0
  fi

  if [[ -z "$startup_file" ]]; then
    if [[ -f "$HOME/.bashrc" ]] && grep -F ".bash_aliases" "$HOME/.bashrc" >/dev/null; then
      startup_file="$HOME/.bash_aliases"
    else
      printf 'Warning: completion installed but not loaded at shell startup. Source %s from your shell startup file.\n' "$completion_target" >&2
      return 0
    fi
  fi

  mkdir -p "$(dirname -- "$startup_file")"

  if [[ -e "$startup_file" && ! -w "$startup_file" ]]; then
    printf 'Warning: completion startup file is not writable: %s\n' "$startup_file" >&2
    return 0
  fi

  if [[ -e "$startup_file" ]] && grep -F "$marker_start" "$startup_file" >/dev/null; then
    printf 'Completion startup already configured: %s\n' "$startup_file"
    return 0
  fi

  {
    printf '\n%s\n' "$marker_start"
    printf '[ -r %q ] && . %q\n' "$completion_target" "$completion_target"
    printf '%s\n' "$marker_end"
  } >>"$startup_file"

  printf 'Configured completion startup: %s\n' "$startup_file"
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$script_dir/bin"
completion_src="$script_dir/completions/cli-tools"
reinstall=0

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --reinstall)
      reinstall=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "unknown argument: $1"
      ;;
  esac
  shift
done

[[ -d "$bin_dir" ]] || die "missing bin directory: $bin_dir"

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

if [[ "$reinstall" -eq 1 ]]; then
  while IFS= read -r target; do
    existing="$(readlink "$target" 2>/dev/null || true)"
    if path_starts_with "$existing" "$bin_dir"; then
      rm -- "$target"
      printf 'Removed: %s -> %s\n' "$target" "$existing"
    fi
  done < <(find "$install_dir" -maxdepth 1 -type l | sort)
fi

installed=0

while IFS= read -r source_cmd; do
  name="$(basename "$source_cmd")"
  target="$install_dir/$name"

  if [[ -e "$target" || -L "$target" ]]; then
    existing="$(readlink "$target" 2>/dev/null || true)"
    if [[ "$existing" != "$source_cmd" ]]; then
      die "refusing to overwrite existing command: $target"
    fi
  fi

  ln -sfn "$source_cmd" "$target"
  printf 'Installed: %s -> %s\n' "$target" "$source_cmd"
  installed=$((installed + 1))
done < <(find "$bin_dir" -maxdepth 1 -type f -perm -u+x | sort)

if [[ "$installed" -eq 0 ]]; then
  die "no executable commands found in: $bin_dir"
fi

if [[ -f "$completion_src" ]]; then
  completion_base="${BASH_COMPLETION_USER_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion}"
  completion_install_dir="$completion_base/completions"
  completion_target="$completion_install_dir/cli-tools"

  mkdir -p "$completion_install_dir"
  [[ -w "$completion_install_dir" ]] || die "completion directory is not writable: $completion_install_dir"

  if [[ -e "$completion_target" || -L "$completion_target" ]]; then
    existing="$(readlink "$completion_target" 2>/dev/null || true)"
    if [[ "$existing" != "$completion_src" ]]; then
      die "refusing to overwrite existing completion: $completion_target"
    fi
  fi

  ln -sfn "$completion_src" "$completion_target"
  printf 'Installed completion: %s -> %s\n' "$completion_target" "$completion_src"
  configure_completion_startup "$completion_target"
fi

if ! path_contains "$install_dir"; then
  printf 'Warning: %s is not in PATH. Add it to your shell startup file.\n' "$install_dir" >&2
fi
