#!/bin/sh
set -eu

CONFIG_DIR=${ZEROCLAW_CONFIG_DIR:-/zeroclaw-data/.zeroclaw}
DATA_DIR=${ZEROCLAW_DATA_DIR:-$CONFIG_DIR/data}
WORKSPACE_DIR=${ZEROCLAW_AGENT_WORKSPACE:-/zeroclaw-data/workspace}
CONFIG_PATH="$CONFIG_DIR/config.toml"

mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$WORKSPACE_DIR"

toml_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

toml_string() {
  printf '"%s"' "$(toml_escape "$1")"
}

toml_bool() {
  case "$(printf '%s' "${1:-false}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) printf 'true' ;;
    *) printf 'false' ;;
  esac
}

toml_array_csv() {
  raw=${1:-}
  if [ -z "$raw" ]; then
    printf '[]'
    return
  fi
  old_ifs=$IFS
  IFS=,
  first=1
  printf '['
  for item in $raw; do
    trimmed=$(printf '%s' "$item" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
    [ -z "$trimmed" ] && continue
    if [ "$first" -eq 0 ]; then
      printf ', '
    fi
    toml_string "$trimmed"
    first=0
  done
  printf ']'
  IFS=$old_ifs
}

toml_array_csv_allow_all() {
  raw=$(printf '%s' "${1:-}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  if [ "$raw" = "*" ]; then
    printf '[]'
    return
  fi
  toml_array_csv "$raw"
}

toml_array_csv_peer_usernames() {
  raw=${1:-}
  if [ -z "$raw" ]; then
    printf '[]'
    return
  fi
  old_ifs=$IFS
  IFS=,
  first=1
  printf '['
  for item in $raw; do
    trimmed=$(printf '%s' "$item" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
    [ -z "$trimmed" ] && continue
    if [ "$first" -eq 0 ]; then
      printf ', '
    fi
    toml_string "$trimmed"
    first=0
  done
  printf ']'
  IFS=$old_ifs
}

first_nonempty() {
  for value in "$@"; do
    if [ -n "${value:-}" ]; then
      printf '%s' "$value"
      return
    fi
  done
}

matrix_stream_mode() {
  if [ "$(toml_bool "${MATRIX_MULTI_MESSAGE:-false}")" = "true" ]; then
    printf 'multi_message'
    return
  fi
  printf '%s' "${MATRIX_STREAM_MODE:-off}"
}

write_mcp_block() {
  if [ "$(toml_bool "${MCP_ENABLED:-false}")" != "true" ] || [ -z "${MCP_URL:-}" ]; then
    return
  fi

  headers='{}'
  if [ -n "${MCP_GATEWAY_TOKEN:-}" ]; then
    headers="{ Authorization = \"Bearer $(toml_escape "$MCP_GATEWAY_TOKEN")\" }"
  fi

  cat <<EOF

[mcp]
enabled = true
deferred_loading = $(toml_bool "${MCP_DEFERRED_LOADING:-true}")
servers = [
  { name = "$(toml_escape "${MCP_SERVER_NAME:-home}")", transport = "$(toml_escape "${MCP_TRANSPORT:-sse}")", url = "$(toml_escape "$MCP_URL")", headers = $headers, tool_timeout_secs = ${MCP_TOOL_TIMEOUT_SECS:-120} },
]
EOF
}

cat > "$CONFIG_PATH" <<EOF
schema_version = 3
workspace_dir = "$(toml_escape "$WORKSPACE_DIR")"
config_path = "$(toml_escape "$CONFIG_PATH")"
default_model_provider = "deepseek.text"
default_model = "$(toml_escape "${DEEPSEEK_MODEL:-deepseek-chat}")"
default_temperature = 0.7

[heartbeat]
enabled = $(toml_bool "${HEARTBEAT_ENABLED:-false}")
agent = "main"
interval_minutes = ${HEARTBEAT_INTERVAL_MINUTES:-30}
two_phase = $(toml_bool "${HEARTBEAT_TWO_PHASE:-true}")
message = "$(toml_escape "${HEARTBEAT_MESSAGE:-}")"
adaptive = $(toml_bool "${HEARTBEAT_ADAPTIVE:-false}")
min_interval_minutes = ${HEARTBEAT_MIN_INTERVAL_MINUTES:-5}
max_interval_minutes = ${HEARTBEAT_MAX_INTERVAL_MINUTES:-120}
deadman_timeout_minutes = ${HEARTBEAT_DEADMAN_TIMEOUT_MINUTES:-0}
max_run_history = ${HEARTBEAT_MAX_RUN_HISTORY:-100}
load_session_context = $(toml_bool "${HEARTBEAT_LOAD_SESSION_CONTEXT:-false}")
task_timeout_secs = ${HEARTBEAT_TASK_TIMEOUT_SECS:-600}

[gateway]
port = 42617
host = "[::]"
allow_public_bind = true
require_pairing = false
request_timeout_secs = 120
long_running_request_timeout_secs = 900

[pacing]
loop_ignore_tools = $(toml_array_csv "${PACING_LOOP_IGNORE_TOOLS:-home__job_status}")
loop_detection_enabled = $(toml_bool "${PACING_LOOP_DETECTION_ENABLED:-true}")
loop_detection_window_size = ${PACING_LOOP_DETECTION_WINDOW_SIZE:-20}
loop_detection_max_repeats = ${PACING_LOOP_DETECTION_MAX_REPEATS:-3}

[providers.models.deepseek.text]
uri = "$(toml_escape "${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}")"
model = "$(toml_escape "${DEEPSEEK_MODEL:-deepseek-chat}")"
api_key = "$(toml_escape "${ZEROCLAW_providers__models__deepseek__text__api_key:-}")"
wire_api = "$(toml_escape "${DEEPSEEK_WIRE_API:-chat_completions}")"
timeout_secs = 120

[providers.models.custom.vision]
uri = "$(toml_escape "${VISION_BASE_URL:-https://api.openai.com/v1}")"
model = "$(toml_escape "${VISION_MODEL:-gpt-4o}")"
api_key = "$(toml_escape "$(first_nonempty "${ZEROCLAW_providers__models__custom__vision__api_key:-}" "${ZEROCLAW_providers__models__openai__vision__api_key:-}")")"
wire_api = "$(toml_escape "${VISION_WIRE_API:-chat_completions}")"
timeout_secs = 120

[[model_routes]]
hint = "vision"
model_provider = "custom.vision"
model = "$(toml_escape "${VISION_MODEL:-gpt-4o}")"

[query_classification]
enabled = true

[[query_classification.rules]]
hint = "vision"
patterns = ["[IMAGE:", "[Image:"]
keywords = ["image attached", "attached image", "will be processed by vision model"]
priority = 100

[multimodal]
max_images = ${VISION_MAX_IMAGES:-4}
max_image_size_mb = ${VISION_MAX_IMAGE_SIZE_MB:-5}
max_image_turns = ${VISION_MAX_IMAGE_TURNS:-2}
allow_remote_fetch = $(toml_bool "${VISION_ALLOW_REMOTE_FETCH:-false}")
vision_model_provider = "custom.vision"
vision_model = "$(toml_escape "${VISION_MODEL:-gpt-4o}")"

[media_pipeline]
enabled = true
transcribe_audio = true
describe_images = true
summarize_video = true

[channels]
ack_reactions = $(toml_bool "${MATRIX_ACK_REACTIONS:-true}")

[channels.matrix.home]
enabled = true
homeserver = "$(toml_escape "${MATRIX_HOMESERVER:-}")"
user_id = "$(toml_escape "${MATRIX_USER_ID:-}")"
device_id = "$(toml_escape "${MATRIX_DEVICE_ID:-}")"
allowed_rooms = $(toml_array_csv_allow_all "${MATRIX_ALLOWED_ROOMS:-}")
mention_only = $(toml_bool "${MATRIX_MENTION_ONLY:-false}")
interrupt_on_new_message = $(toml_bool "${MATRIX_INTERRUPT_ON_NEW_MESSAGE:-true}")
reply_in_thread = $(toml_bool "${MATRIX_REPLY_IN_THREAD:-true}")
ack_reactions = $(toml_bool "${MATRIX_ACK_REACTIONS:-true}")
stream_mode = "$(toml_escape "$(matrix_stream_mode)")"
multi_message_delay_ms = ${MATRIX_MULTI_MESSAGE_DELAY_MS:-800}
approval_timeout_secs = 3600
recovery_key = "$(toml_escape "$(first_nonempty "${MATRIX_RECOVERY_KEY:-}" "${MATRIX_RECOVER_KEY:-}")")"

[agents.main]
enabled = true
model_provider = "deepseek.text"
risk_profile = "root"
runtime_profile = "daemon"
channels = ["matrix.home"]

[agents.main.workspace]
path = "$(toml_escape "$WORKSPACE_DIR")"
unrestricted_filesystem = true

[agents.main.memory]
backend = "sqlite"

[peer_groups.matrix_home]
channel = "matrix.home"
agents = ["main"]
external_peers = $(toml_array_csv_peer_usernames "$(first_nonempty "${MATRIX_EXTERNAL_PEERS:-}" "${MATRIX_PEERS:-}")")

[risk_profiles.root]
level = "full"
workspace_only = false
allowed_commands = ["*"]
forbidden_paths = []
require_approval_for_medium_risk = false
block_high_risk_commands = false
shell_env_passthrough = ["PATH", "HOME", "LANG", "MCP_GATEWAY_TOKEN"]
auto_approve = ["*"]
always_ask = []
allowed_roots = ["/"]
allowed_tools = []
excluded_tools = []
sandbox_enabled = false
sandbox_backend = "none"

[runtime_profiles.daemon]
agentic = true
max_tool_iterations = 50
max_actions_per_hour = 4294967295
max_cost_per_day_cents = 1000000
shell_timeout_secs = 300
max_delegation_depth = 3
delegation_timeout_secs = 300
agentic_timeout_secs = 900
max_history_messages = 80
max_context_tokens = 120000
parallel_tools = true
tool_dispatcher = "auto"
max_tool_result_chars = 60000
keep_tool_context_turns = 4
memory_recall_limit = 8

[runtime]
kind = "native"
reasoning_enabled = false

[shell_tool]
timeout_secs = 300
EOF

write_mcp_block >> "$CONFIG_PATH"

if [ "${RENDER_ONLY:-false}" = "true" ]; then
  exit 0
fi

exec zeroclaw daemon
