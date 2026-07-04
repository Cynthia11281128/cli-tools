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
  ./install.sh --check

Install the cli-tools entrypoint onto PATH using a symlink.

Options:
  --reinstall  Reinstall the cli-tools entrypoint and Bash completion.
  --check      Check whether cli-tools and its Bash completion are installed.
  -h, --help   Show this help.
USAGE
}

path_contains() {
  case ":$PATH:" in
    *":$1:"*) return 0 ;;
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

select_install_dir() {
  if [[ -n "${TOOLS_INSTALL_DIR:-}" ]]; then
    printf '%s\n' "$TOOLS_INSTALL_DIR"
  elif [[ -d "$HOME/.local/bin" && -w "$HOME/.local/bin" ]] && path_contains "$HOME/.local/bin"; then
    printf '%s\n' "$HOME/.local/bin"
  elif [[ -n "${CONDA_PREFIX:-}" && -d "$CONDA_PREFIX/bin" && -w "$CONDA_PREFIX/bin" ]] && path_contains "$CONDA_PREFIX/bin"; then
    printf '%s\n' "$CONDA_PREFIX/bin"
  elif [[ -d "$HOME/miniconda3/bin" && -w "$HOME/miniconda3/bin" ]] && path_contains "$HOME/miniconda3/bin"; then
    printf '%s\n' "$HOME/miniconda3/bin"
  else
    printf '%s\n' "$HOME/.local/bin"
  fi
}

completion_target_path() {
  local completion_base="${BASH_COMPLETION_USER_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion}"
  printf '%s/completions/cli-tools\n' "$completion_base"
}

ensure_installable_symlink() {
  local target="$1"
  local source="$2"
  local label="$3"
  local existing

  if [[ -e "$target" || -L "$target" ]]; then
    existing="$(readlink "$target" 2>/dev/null || true)"
    if [[ "$existing" != "$source" ]]; then
      die "refusing to overwrite existing $label: $target"
    fi
  fi
}

install_symlink() {
  local source="$1"
  local target="$2"
  local label="$3"

  mkdir -p "$(dirname -- "$target")"
  [[ -w "$(dirname -- "$target")" ]] || die "$label directory is not writable: $(dirname -- "$target")"
  ensure_installable_symlink "$target" "$source" "$label"
  ln -sfn "$source" "$target"
  printf 'Installed %s: %s -> %s\n' "$label" "$target" "$source"
}

issues=()

add_issue() {
  issues+=("$*")
}

check_expected_symlink() {
  local target="$1"
  local source="$2"
  local label="$3"
  local existing

  if [[ ! -e "$target" && ! -L "$target" ]]; then
    add_issue "missing $label: $target"
    return 0
  fi

  if [[ ! -L "$target" ]]; then
    add_issue "conflict: $target exists but is not a symlink"
    return 0
  fi

  existing="$(readlink "$target" 2>/dev/null || true)"
  if [[ "$existing" != "$source" ]]; then
    add_issue "conflict: $target points to $existing; expected $source"
  fi
}

run_check() {
  local cli_tools_target="$1"
  local cli_tools_src="$2"
  local completion_target="$3"
  local completion_src="$4"
  local resolved

  check_expected_symlink "$cli_tools_target" "$cli_tools_src" "command"

  resolved="$(command -v cli-tools 2>/dev/null || true)"
  if [[ "$resolved" != "$cli_tools_target" ]]; then
    if [[ -z "$resolved" ]]; then
      add_issue "PATH does not resolve cli-tools; expected $cli_tools_target"
    else
      add_issue "PATH resolves cli-tools to $resolved; expected $cli_tools_target"
    fi
  fi

  if [[ -f "$completion_src" ]]; then
    check_expected_symlink "$completion_target" "$completion_src" "completion"
  fi

  if [[ "${#issues[@]}" -eq 0 ]]; then
    printf 'Install check passed.\n'
    return 0
  fi

  printf 'Install check failed:\n' >&2
  printf '  - %s\n' "${issues[@]}" >&2
  printf 'Run ./install.sh --reinstall after resolving conflicts.\n' >&2
  return 1
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$script_dir/bin"
cli_tools_src="$bin_dir/cli-tools"
completion_src="$script_dir/completions/cli-tools"
mode="install"

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --reinstall)
      [[ "$mode" == "install" ]] || die "only one mode can be selected"
      mode="reinstall"
      ;;
    --check)
      [[ "$mode" == "install" ]] || die "only one mode can be selected"
      mode="check"
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
[[ -x "$cli_tools_src" && -f "$cli_tools_src" ]] || die "missing executable entrypoint: $cli_tools_src"

install_dir="$(select_install_dir)"
cli_tools_target="$install_dir/cli-tools"
completion_target="$(completion_target_path)"

if [[ "$mode" == "check" ]]; then
  run_check "$cli_tools_target" "$cli_tools_src" "$completion_target" "$completion_src"
  exit $?
fi

install_symlink "$cli_tools_src" "$cli_tools_target" "command"

if [[ -f "$completion_src" ]]; then
  install_symlink "$completion_src" "$completion_target" "completion"
  configure_completion_startup "$completion_target"
fi

if ! path_contains "$install_dir"; then
  printf 'Warning: %s is not in PATH. Add it to your shell startup file.\n' "$install_dir" >&2
fi
