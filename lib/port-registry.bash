port_die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

port_warn() {
  printf 'warning: %s\n' "$*" >&2
}

port_require_cmd() {
  command -v "$1" >/dev/null 2>&1 || port_die "missing required command: $1"
}

port_resolve_self() {
  local source="$1"
  local dir link

  while [[ -L "$source" ]]; do
    dir="$(CDPATH= cd -- "$(dirname -- "$source")" && pwd)" || return 1
    link="$(readlink -- "$source")" || return 1

    if [[ "$link" == /* ]]; then
      source="$link"
    else
      source="$dir/$link"
    fi
  done

  dir="$(CDPATH= cd -- "$(dirname -- "$source")" && pwd)" || return 1
  printf '%s/%s\n' "$dir" "$(basename -- "$source")"
}

port_registry_setup() {
  local source_path lib_dir

  source_path="$(port_resolve_self "${BASH_SOURCE[0]}")" ||
    port_die "failed to resolve port registry helper path"
  lib_dir="$(dirname -- "$source_path")"

  PORT_TOOLS_ROOT="$(CDPATH= cd -- "$lib_dir/.." && pwd)" ||
    port_die "failed to resolve cli-tools root"
  PORT_CACHE_ROOT="$PORT_TOOLS_ROOT/.cache"
  PORT_CACHE_DIR="$PORT_CACHE_ROOT/ports"
  PORT_LOG_DIR="$PORT_CACHE_DIR/logs"
  PORT_REGISTRY="$PORT_CACHE_DIR/registry.tsv"
  PORT_LOCK_DIR="$PORT_CACHE_ROOT/ports.lock"

  port_require_cmd ss
  port_require_cmd setsid
  port_require_cmd ps
  port_require_cmd awk
  port_require_cmd sed
  port_require_cmd date
  port_require_cmd mkdir
  port_require_cmd mv
  port_require_cmd rm
}

port_registry_init() {
  mkdir -p "$PORT_LOG_DIR"
}

port_registry_lock() {
  mkdir -p "$PORT_CACHE_ROOT"

  local attempts=0 lock_pid=""
  while ! mkdir "$PORT_LOCK_DIR" 2>/dev/null; do
    if [[ -f "$PORT_LOCK_DIR/pid" ]]; then
      IFS= read -r lock_pid <"$PORT_LOCK_DIR/pid" || lock_pid=""
      if [[ "$lock_pid" =~ ^[0-9]+$ ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
        rm -rf -- "$PORT_LOCK_DIR"
        continue
      fi
    fi

    attempts=$((attempts + 1))
    if (( attempts >= 50 )); then
      port_die "failed to acquire port registry lock: $PORT_LOCK_DIR"
    fi
    sleep 0.1
  done

  printf '%s\n' "$$" >"$PORT_LOCK_DIR/pid"
  trap port_registry_unlock EXIT
}

port_registry_unlock() {
  if [[ -n "${PORT_LOCK_DIR:-}" && -d "$PORT_LOCK_DIR" ]]; then
    rm -rf -- "$PORT_LOCK_DIR"
  fi
}

port_validate_name() {
  local name="$1"

  [[ -n "$name" ]] || port_die "name is required"
  [[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] ||
    port_die "invalid name: $name; use only letters, numbers, '.', '_', and '-'"
}

port_validate_port() {
  local port="$1"

  [[ "$port" =~ ^[0-9]+$ ]] ||
    port_die "invalid port: $port; expected an integer from 1 to 65535"
  (( port >= 1 && port <= 65535 )) ||
    port_die "invalid port: $port; expected an integer from 1 to 65535"
}

port_validate_command() {
  local command_name="$1"

  [[ -n "$command_name" ]] || port_die "command is required"

  if [[ "$command_name" == */* ]]; then
    [[ -x "$command_name" && -f "$command_name" ]] ||
      port_die "command is not executable: $command_name"
  else
    command -v "$command_name" >/dev/null 2>&1 ||
      port_die "missing command: $command_name"
  fi
}

port_format_command() {
  local formatted=()
  local arg

  for arg in "$@"; do
    printf -v arg '%q' "$arg"
    formatted+=("$arg")
  done

  local IFS=' '
  printf '%s' "${formatted[*]}"
}

port_service_alive() {
  local pgid="$1"

  [[ "$pgid" =~ ^[0-9]+$ ]] || return 1
  kill -0 -- "-$pgid" 2>/dev/null
}

port_pid_alive() {
  local pid="$1"

  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

port_is_listening() {
  local port="$1"
  local first_line

  first_line="$(ss -ltnH "sport = :$port" 2>/dev/null | sed -n '1p')"
  [[ -n "$first_line" ]]
}

port_color_enabled() {
  case "${CLI_TOOLS_COLOR:-auto}" in
    always) return 0 ;;
    never) return 1 ;;
    auto|"") [[ -t 1 ]] ;;
    *) [[ -t 1 ]] ;;
  esac
}

port_registry_line_by_name() {
  local target_name="$1"
  local name port pid start_time log_path command_text

  [[ -f "$PORT_REGISTRY" ]] || return 1

  while IFS=$'\t' read -r name port pid start_time log_path command_text || [[ -n "$name" ]]; do
    [[ -n "$name" ]] || continue
    if [[ "$name" == "$target_name" ]]; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$name" "$port" "$pid" "$start_time" "$log_path" "$command_text"
      return 0
    fi
  done <"$PORT_REGISTRY"

  return 1
}

port_registry_active_name_exists() {
  local target_name="$1"
  local line name port pid start_time log_path command_text

  line="$(port_registry_line_by_name "$target_name" || true)"
  [[ -n "$line" ]] || return 1

  IFS=$'\t' read -r name port pid start_time log_path command_text <<<"$line"
  port_service_alive "$pid"
}

port_registry_active_port_exists() {
  local target_port="$1"
  local name port pid start_time log_path command_text

  [[ -f "$PORT_REGISTRY" ]] || return 1

  while IFS=$'\t' read -r name port pid start_time log_path command_text || [[ -n "$name" ]]; do
    [[ -n "$name" ]] || continue
    if [[ "$port" == "$target_port" ]] && port_service_alive "$pid"; then
      return 0
    fi
  done <"$PORT_REGISTRY"

  return 1
}

port_registry_append() {
  local name="$1"
  local port="$2"
  local pid="$3"
  local start_time="$4"
  local log_path="$5"
  local command_text="$6"

  port_registry_init
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$name" "$port" "$pid" "$start_time" "$log_path" "$command_text" >>"$PORT_REGISTRY"
}

port_registry_remove_name() {
  local target_name="$1"
  local tmp="$PORT_REGISTRY.$$"
  local name port pid start_time log_path command_text

  mkdir -p "$PORT_CACHE_DIR"
  : >"$tmp"

  if [[ -f "$PORT_REGISTRY" ]]; then
    while IFS=$'\t' read -r name port pid start_time log_path command_text || [[ -n "$name" ]]; do
      [[ -n "$name" ]] || continue
      if [[ "$name" != "$target_name" ]]; then
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
          "$name" "$port" "$pid" "$start_time" "$log_path" "$command_text" >>"$tmp"
      fi
    done <"$PORT_REGISTRY"
  fi

  if [[ -s "$tmp" ]]; then
    mv "$tmp" "$PORT_REGISTRY"
  else
    rm -f -- "$tmp" "$PORT_REGISTRY"
  fi
}

port_registry_cleanup_stale() {
  local tmp="$PORT_REGISTRY.$$"
  local name port pid start_time log_path command_text
  local kept=0

  [[ -f "$PORT_REGISTRY" ]] || return 0

  mkdir -p "$PORT_CACHE_DIR"
  : >"$tmp"

  while IFS=$'\t' read -r name port pid start_time log_path command_text || [[ -n "$name" ]]; do
    [[ -n "$name" ]] || continue
    if port_service_alive "$pid"; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$name" "$port" "$pid" "$start_time" "$log_path" "$command_text" >>"$tmp"
      kept=$((kept + 1))
    fi
  done <"$PORT_REGISTRY"

  if (( kept > 0 )); then
    mv "$tmp" "$PORT_REGISTRY"
  else
    rm -f -- "$tmp" "$PORT_REGISTRY"
  fi
}

port_registry_count_entries() {
  local count=0
  local name port pid start_time log_path command_text

  [[ -f "$PORT_REGISTRY" ]] || {
    printf '0\n'
    return 0
  }

  while IFS=$'\t' read -r name port pid start_time log_path command_text || [[ -n "$name" ]]; do
    [[ -n "$name" ]] || continue
    count=$((count + 1))
  done <"$PORT_REGISTRY"

  printf '%s\n' "$count"
}

port_registry_print_entries() {
  local name port pid start_time log_path command_text status first_entry
  local blue="" reset=""

  if port_color_enabled; then
    blue=$'\033[34m'
    reset=$'\033[0m'
  fi

  printf '%-20s %-6s %-10s %-8s %-25s %s\n' \
    "NAME" "PORT" "STATUS" "PID" "STARTED" "LOG"

  first_entry=1
  while IFS=$'\t' read -r name port pid start_time log_path command_text || [[ -n "$name" ]]; do
    [[ -n "$name" ]] || continue
    if (( first_entry )); then
      first_entry=0
    else
      printf '\n'
    fi
    status="running"
    if port_is_listening "$port"; then
      status="listening"
    fi
    printf '%b%-20s%b ' "$blue" "$name" "$reset"
    printf '%b%-6s%b ' "$blue" "$port" "$reset"
    printf '%-10s %-8s %-25s %s\n' \
      "$status" "$pid" "$start_time" "$log_path"
    printf '  command: %s\n' "$command_text"
  done <"$PORT_REGISTRY"
}

port_parse_registry_line() {
  IFS=$'\t' read -r PORT_ENTRY_NAME PORT_ENTRY_PORT PORT_ENTRY_PID \
    PORT_ENTRY_START_TIME PORT_ENTRY_LOG_PATH PORT_ENTRY_COMMAND <<<"$1"
}

port_registry_setup
