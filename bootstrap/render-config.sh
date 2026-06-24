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
  printf '%s' "${MATRIX_STREAM_MODE:-multi_message}"
}

validate_provider_segment() {
  name=$1
  value=$2
  case "$value" in
    ''|*[!A-Za-z0-9_-]*)
      printf 'Invalid %s "%s"; use only letters, numbers, underscores, or hyphens.\n' "$name" "$value" >&2
      exit 1
      ;;
  esac
}

validate_unsigned_int() {
  name=$1
  value=$2
  case "$value" in
    ''|*[!0-9]*)
      printf 'Invalid %s "%s"; use a whole number.\n' "$name" "$value" >&2
      exit 1
      ;;
  esac
}

MODEL_PROVIDER_FAMILY=$(first_nonempty "${MODEL_PROVIDER_FAMILY:-}" "deepseek")
MODEL_PROVIDER_ALIAS=$(first_nonempty "${MODEL_PROVIDER_ALIAS:-}" "text")
MODEL_PROVIDER_MODEL=$(first_nonempty "${MODEL_PROVIDER_MODEL:-}" "deepseek-chat")
MODEL_PROVIDER_BASE_URL=$(first_nonempty "${MODEL_PROVIDER_BASE_URL:-}")
MODEL_PROVIDER_API_KEY=$(first_nonempty "${MODEL_PROVIDER_API_KEY:-}")
MODEL_PROVIDER_WIRE_API=$(first_nonempty "${MODEL_PROVIDER_WIRE_API:-}")
MODEL_PROVIDER_TIMEOUT_SECS=$(first_nonempty "${MODEL_PROVIDER_TIMEOUT_SECS:-}" "120")
MODEL_PROVIDER_KIND=$(first_nonempty "${MODEL_PROVIDER_KIND:-}" "")
MODEL_PROVIDER_TEMPERATURE=$(first_nonempty "${MODEL_PROVIDER_TEMPERATURE:-}" "")
MODEL_PROVIDER_MAX_TOKENS=$(first_nonempty "${MODEL_PROVIDER_MAX_TOKENS:-}" "")
MODEL_PROVIDER_REQUIRES_OPENAI_AUTH=$(first_nonempty "${MODEL_PROVIDER_REQUIRES_OPENAI_AUTH:-}" "false")
MODEL_PROVIDER_FALLBACK=$(first_nonempty "${MODEL_PROVIDER_FALLBACK:-}" "")
MODEL_PROVIDER_FALLBACK_MODELS=$(first_nonempty "${MODEL_PROVIDER_FALLBACK_MODELS:-}" "")
MODEL_PROVIDER_EXTRA_HEADERS=$(first_nonempty "${MODEL_PROVIDER_EXTRA_HEADERS:-}" "")
MODEL_PROVIDER_MERGE_SYSTEM_INTO_USER=$(first_nonempty "${MODEL_PROVIDER_MERGE_SYSTEM_INTO_USER:-}" "false")
MODEL_PROVIDER_PROVIDER_EXTRA=$(first_nonempty "${MODEL_PROVIDER_PROVIDER_EXTRA:-}" "")
MODEL_PROVIDER_PRICING=$(first_nonempty "${MODEL_PROVIDER_PRICING:-}" "")
MODEL_PROVIDER_NATIVE_TOOLS=$(first_nonempty "${MODEL_PROVIDER_NATIVE_TOOLS:-}" "")
MODEL_PROVIDER_THINK=$(first_nonempty "${MODEL_PROVIDER_THINK:-}" "")
MODEL_PROVIDER_CHAT_TEMPLATE_KWARGS=$(first_nonempty "${MODEL_PROVIDER_CHAT_TEMPLATE_KWARGS:-}" "")
MODEL_PROVIDER_TLS_CA_CERT_PATH=$(first_nonempty "${MODEL_PROVIDER_TLS_CA_CERT_PATH:-}" "")
MODEL_PROVIDER_AUTH_MODE=$(first_nonempty "${MODEL_PROVIDER_AUTH_MODE:-}" "")
MODEL_PROVIDER_OAUTH_CLIENT_ID=$(first_nonempty "${MODEL_PROVIDER_OAUTH_CLIENT_ID:-}" "")
MODEL_PROVIDER_OAUTH_CLIENT_SECRET=$(first_nonempty "${MODEL_PROVIDER_OAUTH_CLIENT_SECRET:-}" "")
MODEL_PROVIDER_OAUTH_PROJECT=$(first_nonempty "${MODEL_PROVIDER_OAUTH_PROJECT:-}" "")
MODEL_PROVIDER_NUM_CTX=$(first_nonempty "${MODEL_PROVIDER_NUM_CTX:-}" "")
MODEL_PROVIDER_NUM_PREDICT=$(first_nonempty "${MODEL_PROVIDER_NUM_PREDICT:-}" "")
MODEL_PROVIDER_TEMPERATURE_OVERRIDE=$(first_nonempty "${MODEL_PROVIDER_TEMPERATURE_OVERRIDE:-}" "")
MODEL_PROVIDER_REF="${MODEL_PROVIDER_FAMILY}.${MODEL_PROVIDER_ALIAS}"
VISION_ENABLED=$(first_nonempty "${VISION_ENABLED:-}" "true")
VISION_PROVIDER_FAMILY=$(first_nonempty "${VISION_PROVIDER_FAMILY:-}" "custom")
VISION_PROVIDER_ALIAS=$(first_nonempty "${VISION_PROVIDER_ALIAS:-}" "vision")
VISION_PROVIDER_REF="${VISION_PROVIDER_FAMILY}.${VISION_PROVIDER_ALIAS}"
VISION_TIMEOUT_SECS=$(first_nonempty "${VISION_TIMEOUT_SECS:-}" "120")
SHELL_TIMEOUT_SECS=$(first_nonempty "${SHELL_TIMEOUT_SECS:-}" "300")
SHELL_TOOL_TIMEOUT_SECS=$(first_nonempty "${SHELL_TOOL_TIMEOUT_SECS:-}" "$SHELL_TIMEOUT_SECS")

validate_provider_segment "MODEL_PROVIDER_FAMILY" "$MODEL_PROVIDER_FAMILY"
validate_provider_segment "MODEL_PROVIDER_ALIAS" "$MODEL_PROVIDER_ALIAS"
validate_provider_segment "VISION_PROVIDER_FAMILY" "$VISION_PROVIDER_FAMILY"
validate_provider_segment "VISION_PROVIDER_ALIAS" "$VISION_PROVIDER_ALIAS"
validate_unsigned_int "MODEL_PROVIDER_TIMEOUT_SECS" "$MODEL_PROVIDER_TIMEOUT_SECS"
if [ -n "$MODEL_PROVIDER_MAX_TOKENS" ]; then validate_unsigned_int "MODEL_PROVIDER_MAX_TOKENS" "$MODEL_PROVIDER_MAX_TOKENS"; fi
if [ -n "$MODEL_PROVIDER_NUM_CTX" ]; then validate_unsigned_int "MODEL_PROVIDER_NUM_CTX" "$MODEL_PROVIDER_NUM_CTX"; fi
validate_unsigned_int "VISION_TIMEOUT_SECS" "$VISION_TIMEOUT_SECS"
validate_unsigned_int "SHELL_TIMEOUT_SECS" "$SHELL_TIMEOUT_SECS"
validate_unsigned_int "SHELL_TOOL_TIMEOUT_SECS" "$SHELL_TOOL_TIMEOUT_SECS"

write_model_provider_block() {
  cat <<EOF
[providers.models.${MODEL_PROVIDER_FAMILY}.${MODEL_PROVIDER_ALIAS}]
model = "$(toml_escape "$MODEL_PROVIDER_MODEL")"
EOF
  if [ -n "$MODEL_PROVIDER_BASE_URL" ]; then
    printf 'uri = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_BASE_URL")"
  fi
  if [ -n "$MODEL_PROVIDER_API_KEY" ]; then
    printf 'api_key = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_API_KEY")"
  fi
  if [ -n "$MODEL_PROVIDER_WIRE_API" ]; then
    printf 'wire_api = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_WIRE_API")"
  fi
  if [ -n "$MODEL_PROVIDER_KIND" ]; then
    printf 'kind = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_KIND")"
  fi
  printf 'timeout_secs = %s\n' "$MODEL_PROVIDER_TIMEOUT_SECS"
  if [ -n "$MODEL_PROVIDER_TEMPERATURE" ]; then printf 'temperature = %s\n' "$MODEL_PROVIDER_TEMPERATURE"; fi
  if [ -n "$MODEL_PROVIDER_MAX_TOKENS" ]; then printf 'max_tokens = %s\n' "$MODEL_PROVIDER_MAX_TOKENS"; fi
  if [ "$(toml_bool "$MODEL_PROVIDER_REQUIRES_OPENAI_AUTH")" = "true" ]; then printf 'requires_openai_auth = true\n'; fi
  if [ -n "$MODEL_PROVIDER_FALLBACK" ]; then printf 'fallback = %s\n' "$MODEL_PROVIDER_FALLBACK"; fi
  if [ -n "$MODEL_PROVIDER_FALLBACK_MODELS" ]; then printf 'fallback_models = %s\n' "$MODEL_PROVIDER_FALLBACK_MODELS"; fi
  if [ -n "$MODEL_PROVIDER_EXTRA_HEADERS" ]; then printf 'extra_headers = %s\n' "$MODEL_PROVIDER_EXTRA_HEADERS"; fi
  if [ "$(toml_bool "$MODEL_PROVIDER_MERGE_SYSTEM_INTO_USER")" = "true" ]; then printf 'merge_system_into_user = true\n'; fi
  if [ -n "$MODEL_PROVIDER_PROVIDER_EXTRA" ]; then printf 'provider_extra = %s\n' "$MODEL_PROVIDER_PROVIDER_EXTRA"; fi
  if [ -n "$MODEL_PROVIDER_PRICING" ]; then printf 'pricing = %s\n' "$MODEL_PROVIDER_PRICING"; fi
  if [ -n "$MODEL_PROVIDER_NATIVE_TOOLS" ]; then printf 'native_tools = %s\n' "$(toml_bool "$MODEL_PROVIDER_NATIVE_TOOLS")"; fi
  if [ -n "$MODEL_PROVIDER_THINK" ]; then printf 'think = %s\n' "$(toml_bool "$MODEL_PROVIDER_THINK")"; fi
  if [ -n "$MODEL_PROVIDER_CHAT_TEMPLATE_KWARGS" ]; then printf 'chat_template_kwargs = %s\n' "$MODEL_PROVIDER_CHAT_TEMPLATE_KWARGS"; fi
  if [ -n "$MODEL_PROVIDER_TLS_CA_CERT_PATH" ]; then printf 'tls_ca_cert_path = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_TLS_CA_CERT_PATH")"; fi
  if [ -n "$MODEL_PROVIDER_AUTH_MODE" ]; then printf 'auth_mode = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_AUTH_MODE")"; fi
  if [ -n "$MODEL_PROVIDER_OAUTH_CLIENT_ID" ]; then printf 'oauth_client_id = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_OAUTH_CLIENT_ID")"; fi
  if [ -n "$MODEL_PROVIDER_OAUTH_CLIENT_SECRET" ]; then printf 'oauth_client_secret = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_OAUTH_CLIENT_SECRET")"; fi
  if [ -n "$MODEL_PROVIDER_OAUTH_PROJECT" ]; then printf 'oauth_project = "%s"\n' "$(toml_escape "$MODEL_PROVIDER_OAUTH_PROJECT")"; fi
  if [ -n "$MODEL_PROVIDER_NUM_CTX" ]; then printf 'num_ctx = %s\n' "$MODEL_PROVIDER_NUM_CTX"; fi
  if [ -n "$MODEL_PROVIDER_NUM_PREDICT" ]; then printf 'num_predict = %s\n' "$MODEL_PROVIDER_NUM_PREDICT"; fi
  if [ -n "$MODEL_PROVIDER_TEMPERATURE_OVERRIDE" ]; then printf 'temperature_override = %s\n' "$MODEL_PROVIDER_TEMPERATURE_OVERRIDE"; fi
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
default_model_provider = "$(toml_escape "$MODEL_PROVIDER_REF")"
default_model = "$(toml_escape "$MODEL_PROVIDER_MODEL")"
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

EOF

write_model_provider_block >> "$CONFIG_PATH"

if [ "$(toml_bool "$VISION_ENABLED")" = "true" ]; then
cat >> "$CONFIG_PATH" <<EOF

[providers.models.${VISION_PROVIDER_FAMILY}.${VISION_PROVIDER_ALIAS}]
uri = "$(toml_escape "${VISION_BASE_URL:-https://api.openai.com/v1}")"
model = "$(toml_escape "${VISION_MODEL:-gpt-4o}")"
api_key = "$(toml_escape "$(first_nonempty "${ZEROCLAW_providers__models__custom__vision__api_key:-}" "${ZEROCLAW_providers__models__openai__vision__api_key:-}" "${OPENAI_API_KEY:-}")")"
wire_api = "$(toml_escape "${VISION_WIRE_API:-chat_completions}")"
timeout_secs = ${VISION_TIMEOUT_SECS}

[[model_routes]]
hint = "vision"
model_provider = "$(toml_escape "$VISION_PROVIDER_REF")"
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
vision_model_provider = "$(toml_escape "$VISION_PROVIDER_REF")"
vision_model = "$(toml_escape "${VISION_MODEL:-gpt-4o}")"

EOF
else
cat >> "$CONFIG_PATH" <<EOF

[multimodal]
max_images = ${VISION_MAX_IMAGES:-4}
max_image_size_mb = ${VISION_MAX_IMAGE_SIZE_MB:-5}
max_image_turns = ${VISION_MAX_IMAGE_TURNS:-2}
allow_remote_fetch = $(toml_bool "${VISION_ALLOW_REMOTE_FETCH:-false}")

EOF
fi

cat >> "$CONFIG_PATH" <<EOF

[media_pipeline]
enabled = true
transcribe_audio = true
describe_images = true
summarize_video = true

[channels]
ack_reactions = $(toml_bool "${MATRIX_ACK_REACTIONS:-true}")
debounce_ms = ${CHANNEL_DEBOUNCE_MS:-0}

[channels.matrix.home]
enabled = true
homeserver = "$(toml_escape "${MATRIX_HOMESERVER:-}")"
user_id = "$(toml_escape "${MATRIX_USER_ID:-}")"
device_id = "$(toml_escape "${MATRIX_DEVICE_ID:-}")"
allowed_rooms = $(toml_array_csv_allow_all "${MATRIX_ALLOWED_ROOMS:-}")
mention_only = $(toml_bool "${MATRIX_MENTION_ONLY:-false}")
interrupt_on_new_message = $(toml_bool "${MATRIX_INTERRUPT_ON_NEW_MESSAGE:-true}")
reply_in_thread = $(toml_bool "${MATRIX_REPLY_IN_THREAD:-false}")
ack_reactions = $(toml_bool "${MATRIX_ACK_REACTIONS:-true}")
stream_mode = "$(toml_escape "$(matrix_stream_mode)")"
multi_message_delay_ms = ${MATRIX_MULTI_MESSAGE_DELAY_MS:-800}
draft_update_interval_ms = ${MATRIX_DRAFT_UPDATE_INTERVAL_MS:-1500}
approval_timeout_secs = ${MATRIX_APPROVAL_TIMEOUT_SECS:-3600}
excluded_tools = $(toml_array_csv_allow_all "${MATRIX_EXCLUDED_TOOLS:-}")
reply_min_interval_secs = ${MATRIX_REPLY_MIN_INTERVAL_SECS:-0}
reply_queue_depth_max = ${MATRIX_REPLY_QUEUE_DEPTH_MAX:-0}
recovery_key = "$(toml_escape "${MATRIX_RECOVERY_KEY:-}")"

[agents.main]
enabled = true
model_provider = "$(toml_escape "$MODEL_PROVIDER_REF")"
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
external_peers = $(toml_array_csv_peer_usernames "${MATRIX_EXTERNAL_PEERS:-}")

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
shell_timeout_secs = ${SHELL_TIMEOUT_SECS}
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
timeout_secs = ${SHELL_TOOL_TIMEOUT_SECS}
EOF

write_mcp_block >> "$CONFIG_PATH"

if [ "${RENDER_ONLY:-false}" = "true" ]; then
  exit 0
fi

exec zeroclaw daemon
