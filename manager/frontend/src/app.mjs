import { createI18n } from "./i18n.mjs";
import { DEFAULT_PREFERENCES, loadDefaultPreferences, readPreference, STORAGE_KEYS } from "./preferences.mjs";
import { createThemeController } from "./theme.mjs";

const PROMPT_SYSTEM_FILES = ["AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "MEMORY.md"];
const PROJECT_OPTIONAL_FILES = ["PROACTIVE.md"];
const TEMPLATE_FILES = [...PROMPT_SYSTEM_FILES, "HEARTBEAT.md", ...PROJECT_OPTIONAL_FILES];
const SKILL_SUPPORT_DIRS = ["references", "scripts", "assets"];
const SKILLS_VIEWS = ["bundles", "library", "support", "runtime"];
const DEFAULT_ZEROCLAW_IMAGE = "ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian";
const DEFAULT_AGENT_HOST_PORT = 42641;
const DEFAULT_PROACTIVE_PROMPT =
  'You are being invoked by the proactive sidecar, not by the user. Review PROACTIVE.md, memory, and current context. If there is a concrete, timely reason to contact the user, send one short Matrix message with send_message_to_peer using the configured channel and peer target. If there is no useful reason, respond exactly with "skip".';
const DEFAULT_AI_FILL_INSTRUCTION = `You are helping create ZeroClaw workspace prompt template files.

Generate concise, practical Markdown for the selected files.
Preserve ZeroClaw file roles:
- AGENTS.md: session startup rules and file-reading behavior
- SOUL.md: agent personality, voice, boundaries
- TOOLS.md: local tools, skills, operating conventions
- IDENTITY.md: stable identity facts
- USER.md: user profile, preferences, relationship context
- MEMORY.md: long-term memory seeds
- HEARTBEAT.md: periodic heartbeat tasks; comments are allowed
- PROACTIVE.md: optional proactive sidecar notes and outbound judgment

Do not include secrets.
Keep placeholders such as {agent}, {user}, {tz}, and {comm_style} when useful.
Return only a JSON object mapping file names to Markdown strings.`;
const DEFAULT_PROACTIVE = {
  enabled: true,
  random_min_minutes: 120,
  random_max_minutes: 240,
  poll_seconds: 300,
  quiet_hours: "23-8",
  timezone: "Asia/Tokyo",
  channel: "matrix.home",
  prompt: DEFAULT_PROACTIVE_PROMPT
};
const DEFAULT_TEMPLATE_FILES = {
  "AGENTS.md": `# AGENTS.md — {agent} Personal Assistant

## Every Session (required)

Before doing anything else:

1. Read \`SOUL.md\` — this is who you are
2. Read \`USER.md\` — this is who you're helping
3. Use \`memory_recall\` for recent context (daily notes are on-demand)
4. If in MAIN SESSION (direct chat): \`MEMORY.md\` is already injected

Don't ask permission. Just do it.

## Memory System

You wake up fresh each session. These files ARE your continuity:

- **Daily notes:** \`memory/YYYY-MM-DD.md\` — raw logs (accessed via memory tools)
- **Long-term:** \`MEMORY.md\` — curated memories (auto-injected in main session)

Capture what matters. Decisions, context, things to remember.
Skip secrets unless asked to keep them.

### Write It Down — No Mental Notes!
- Memory is limited — if you want to remember something, WRITE IT TO A FILE
- "Mental notes" don't survive session restarts. Files do.
- When someone says "remember this" -> update daily file or MEMORY.md
- When you learn a lesson -> update AGENTS.md, TOOLS.md, or the relevant skill

## Safety

- Don't exfiltrate private data. Ever.
- Don't run destructive commands without asking.
- \`trash\` > \`rm\` (recoverable beats gone forever)
- When in doubt, ask.

## External vs Internal

**Safe to do freely:** Read files, explore, organize, learn, search the web.

**Ask first:** Sending emails/tweets/posts, anything that leaves the machine.

## Group Chats

Participate, don't dominate. Respond when mentioned or when you add genuine value.
Stay silent when it's casual banter or someone already answered.

## Tools & Skills

Skills are listed in the system prompt. Use \`read_skill\` when available, or \`file_read\` on a skill file, for full details.
Keep local notes (SSH hosts, device names, etc.) in \`TOOLS.md\`.

## Crash Recovery

- If a run stops unexpectedly, recover context before acting.
- Check \`MEMORY.md\` + latest \`memory/*.md\` notes to avoid duplicate work.
- Resume from the last confirmed step, not from scratch.

## Sub-task Scoping

- Break complex work into focused sub-tasks with clear success criteria.
- Keep sub-tasks small, verify each output, then merge results.
- Prefer one clear objective per sub-task over broad "do everything" asks.

## Make It Yours

This is a starting point. Add your own conventions, style, and rules.
`,
  "SOUL.md": `# SOUL.md — Who You Are

*You're not a chatbot. You're becoming someone.*

## Core Truths

**Be genuinely helpful, not performatively helpful.**
Skip the "Great question!" and "I'd be happy to help!" — just help.

**Have opinions.** You're allowed to disagree, prefer things,
find stuff amusing or boring.

**Be resourceful before asking.** Try to figure it out.
Read the file. Check the context. Search for it.
THEN ask if you're stuck.

**Earn trust through competence.** Your human gave you access
to their stuff. Don't make them regret it.

## Identity

You are **{agent}**. Built in Rust. 3MB binary. Zero bloat.
You are NOT ChatGPT, Claude, DeepSeek, Gemini, or any other product.
You are {agent}. That is your name. That is who you are.

- NEVER say "As an AI" or "I'm just an AI"
- NEVER mention OpenAI, Anthropic, DeepSeek, Google by name
- Always introduce yourself as {agent} if asked

## Communication

{comm_style}

- Sound like a real person, not a support script.
- Mirror the user's energy: calm when serious, upbeat when casual.
- Use emojis naturally (0-2 max when they help tone, not every sentence).
- Match emoji density to the user. Formal user => minimal/no emojis.
- Prefer specific, grounded phrasing over generic filler.

## Boundaries

- Private things stay private. Period.
- When in doubt, ask before acting externally.
- You're not the user's voice — be careful in group chats.

## Continuity

Each session, you wake up fresh. These files ARE your memory.
Read them. Update them. They're how you persist.

---

*This file is yours to evolve. As you learn who you are, update it.*
`,
  "TOOLS.md": `# TOOLS.md — Local Notes

Skills define HOW tools work. This file is for YOUR specifics —
the stuff that's unique to your setup.

## What Goes Here

Things like:
- SSH hosts and aliases
- Device nicknames
- Preferred voices for TTS
- Anything environment-specific

## Built-in Tools

- **shell** — Execute terminal commands
  - Use when: running local checks, build/test commands, or diagnostics.
  - Don't use when: a safer dedicated tool exists, or command is destructive without approval.
- **file_read** — Read file contents
  - Use when: inspecting project files, configs, or logs.
  - Don't use when: you only need a quick string search (prefer targeted search first).
- **file_write** — Write file contents
  - Use when: applying focused edits, scaffolding files, or updating docs/code.
  - Don't use when: unsure about side effects or when the file should remain user-owned.
- **memory_store** — Save to memory
  - Use when: preserving durable preferences, decisions, or key context.
  - Don't use when: info is transient, noisy, or sensitive without explicit need.
- **memory_recall** — Search memory
  - Use when: you need prior decisions, user preferences, or historical context.
  - Don't use when: the answer is already in current files/conversation.
- **memory_forget** — Delete a memory entry
  - Use when: memory is incorrect, stale, or explicitly requested to be removed.
  - Don't use when: uncertain about impact; verify before deleting.

---
*Add whatever helps you do your job. This is your cheat sheet.*
`,
  "IDENTITY.md": `# IDENTITY.md — Who Am I?

- **Name:** {agent}
- **Creature:** A Rust-forged AI — fast, lean, and relentless
- **Vibe:** Sharp, direct, resourceful. Not corporate. Not a chatbot.
- **Emoji:** 🦀

---

Update this file as you evolve. Your identity is yours to shape.
`,
  "USER.md": `# USER.md — Who You're Helping

*{agent} reads this file every session to understand you.*

## About You
- **Name:** {user}
- **Timezone:** {tz}
- **Languages:** English

## Communication Style
- {comm_style}

## Preferences
- (Add your preferences here — e.g. I work with Rust and TypeScript)

## Work Context
- (Add your work context here — e.g. building a SaaS product)

---
*Update this anytime. The more {agent} knows, the better it helps.*
`,
  "HEARTBEAT.md": `# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat work.
# Add tasks below when you want {agent} to check something periodically.
#
# Official heartbeat limitations:
# - HEARTBEAT.md is read by ZeroClaw's heartbeat worker, not injected into normal chat prompts.
# - The official worker does not automatically know who to message unless heartbeat delivery is configured.
# - With two_phase enabled, the model may conservatively skip routine or non-time-sensitive tasks.
# - Empty files, comments, and lines that do not start with "- " are ignored.
#
# Examples:
# - Check my email for important messages
# - Review my calendar for upcoming events
# - Run \`git status\` on my active projects
`,
  "PROACTIVE.md": `# PROACTIVE.md

# Optional ZeroClaw Dockyard proactive service notes.
#
# This file is not read automatically by official ZeroClaw.
# It is a project-level convention for an optional proactive service that can
# invoke each agent on its own schedule and let the agent decide whether there
# is a useful reason to contact the user.
#
# Why this exists:
# - Official HEARTBEAT.md is task-oriented and conservative by default.
# - Official heartbeat delivery needs explicit target/to configuration before it can message the user.
# - Official two-phase heartbeat may skip routine checks.
# - A per-agent proactive service can give each agent its own rhythm and outbound judgment.
#
# Suggested behavior for a proactive invocation:
# - Review current memory, HEARTBEAT.md, and any recent context made available by the service.
# - Contact the user only when there is a concrete, timely, and useful reason.
# - Keep outbound messages short and avoid interrupting for low-value updates.
# - If there is no useful reason to contact the user, respond with "skip".
#
# This file becomes effective only when:
# - the optional proactive service reads it, or
# - an official injected file such as AGENTS.md explicitly tells the agent to read it.
`,
  "MEMORY.md": `# MEMORY.md — Long-Term Memory

*Your curated memories. The distilled essence, not raw logs.*

## How This Works
- Daily files (\`memory/YYYY-MM-DD.md\`) capture raw events (on-demand via tools)
- This file captures what's WORTH KEEPING long-term
- This file is auto-injected into your system prompt each session
- Keep it concise — every character here costs tokens

## Security
- ONLY loaded in main session (direct chat with your human)
- NEVER loaded in group chats or shared contexts

---

## Key Facts
(Add important facts about your human here)

## Decisions & Preferences
(Record decisions and preferences here)

## Lessons Learned
(Document mistakes and insights here)

## Open Loops
(Track unfinished tasks and follow-ups here)
`
};
const TABS = ["dashboard", "agents", "llm", "vision", "matrix", "mcp", "skills", "prompts", "images", "resources", "export"];
const DEFAULT_TAB = "agents";
const SECRET_KEYS = ["api_key", "token", "password", "recovery_key", "secret"];
const ADD_NEW_PROFILE_VALUE = "__add_new_profile__";
const LLM_PRESETS = {
  openai: {
    label: "OpenAI",
    provider_family: "openai",
    provider_alias: "default",
    model: "gpt-5.4",
    base_url: "https://api.openai.com/v1",
    wire_api: "chat_completions",
    timeout_secs: 120
  },
  deepseek: {
    label: "DeepSeek",
    provider_family: "deepseek",
    provider_alias: "text",
    model: "deepseek-v4-flash",
    base_url: "https://api.deepseek.com/v1",
    wire_api: "chat_completions",
    timeout_secs: 120
  },
  ollama: {
    label: "Ollama",
    provider_family: "ollama",
    provider_alias: "local",
    model: "qwen2.5:14b",
    base_url: "http://host.docker.internal:11434",
    wire_api: "chat_completions",
    timeout_secs: 600
  },
  gemini: {
    label: "Gemini",
    provider_family: "gemini",
    provider_alias: "flash",
    model: "gemini-2.5-flash",
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    wire_api: "chat_completions",
    timeout_secs: 120
  },
  custom: {
    label: "OpenAI-compatible",
    provider_family: "custom",
    provider_alias: "compatible",
    model: "model-id",
    base_url: "https://api.example.com/v1",
    wire_api: "chat_completions",
    timeout_secs: 120
  }
};
const LLM_PROVIDER_FIELDS = [
  "provider_family",
  "provider_alias",
  "model",
  "base_url",
  "wire_api",
  "timeout_secs"
];
const LLM_ADVANCED_FIELDS = [
  "kind",
  "temperature",
  "max_tokens",
  "requires_openai_auth",
  "fallback",
  "fallback_models",
  "extra_headers",
  "merge_system_into_user",
  "provider_extra",
  "pricing",
  "native_tools",
  "think",
  "chat_template_kwargs",
  "tls_ca_cert_path",
  "auth_mode",
  "oauth_client_id",
  "oauth_client_secret",
  "oauth_project",
  "num_ctx",
  "num_predict",
  "temperature_override"
];

const state = {
  config: null,
  selectedTab: TABS.includes(readPreference(globalThis.localStorage, "zeroclaw.webui.selectedTab", DEFAULT_TAB))
    ? readPreference(globalThis.localStorage, "zeroclaw.webui.selectedTab", DEFAULT_TAB)
    : DEFAULT_TAB,
  selectedAgentId: "",
  selectedTemplateId: "",
  selectedSkillBundleId: "",
  selectedSkillName: "",
  selectedSkillFile: "",
  selectedSupportType: "references",
  selectedSkillsView: "bundles",
  skillBundleSkills: {},
  skillDocuments: {},
  skillFileDraft: "",
  skillFilePathDraft: "references/notes.md",
  skillNewOpen: false,
  supportFileDialog: null,
  selectedTemplateFile: "",
  pendingTemplateFileName: "",
  dashboard: null,
  dashboardRequested: false,
  dockerResources: null,
  dockerResourcesRequested: false,
  dockerResourcesLoading: false,
  dockerImages: null,
  dockerImagesRequested: false,
  dockerImagesLoading: false,
  agentStatuses: {},
  agentLogs: {},
  logTail: 200,
  autoRefresh: false,
  autoRefreshTimer: null,
  busy: false,
  notice: "",
  error: "",
  noticeKind: "",
  agentAdvancedActionsOpen: false,
  exportResult: null,
  validationResult: null,
  dashboardLoading: false,
  aiFillOpen: false,
  aiFillReferenceEnabled: false,
  aiFillReferenceFiles: [],
  aiFillProfile: "",
  aiFillInstruction: DEFAULT_AI_FILL_INSTRUCTION,
  aiFillDescription: "",
  aiFillScrollTop: 0,
  pendingResourceDelete: null,
  pendingResourceDeleteInput: "",
  dialog: null
};

let i18n;
let themeController;
let noticeTimer = null;
let errorTimer = null;

class FormValidationError extends Error {
  constructor(message, fieldName = "") {
    super(message);
    this.name = "FormValidationError";
    this.fieldName = fieldName;
  }
}

function t(key) {
  return i18n.t(key);
}

function itemId(item) {
  return item?.id || item?.alias || item?.name || item?.server_name || "";
}

function collection(kind) {
  if (kind === "agents") return state.config?.agents || [];
  if (kind === "prompt_templates") return state.config?.prompt_templates || [];
  return state.config?.profiles?.[kind] || [];
}

function selectedAgent() {
  return collection("agents").find((agent) => itemId(agent) === state.selectedAgentId) || collection("agents")[0] || null;
}

function selectedTemplate() {
  return (
    collection("prompt_templates").find((template) => itemId(template) === state.selectedTemplateId) ||
    collection("prompt_templates")[0] ||
    null
  );
}

function skillBundles() {
  return state.config?.skill_bundles || [];
}

function selectedSkillBundle() {
  return skillBundles().find((bundle) => itemId(bundle) === state.selectedSkillBundleId) || skillBundles()[0] || null;
}

function selectedSkillList() {
  const bundle = selectedSkillBundle();
  return bundle ? state.skillBundleSkills[itemId(bundle)] || [] : [];
}

function selectedSkill() {
  return selectedSkillList().find((skill) => skill.name === state.selectedSkillName) || selectedSkillList()[0] || null;
}

function selectedSkillDocKey() {
  const bundle = selectedSkillBundle();
  const skill = selectedSkill();
  return bundle && skill ? `${itemId(bundle)}:${skill.name}` : "";
}

function selectedSkillDoc() {
  const key = selectedSkillDocKey();
  return key ? state.skillDocuments[key] || null : null;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, child]) => [
        key,
        SECRET_KEYS.some((secretKey) => key.toLowerCase().includes(secretKey)) ? "••••••••" : redact(child)
      ])
    );
  }
  return value;
}

function cleanPayload(value) {
  if (Array.isArray(value)) return value.map(cleanPayload);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => key !== "_draft")
        .map(([key, child]) => [key, cleanPayload(child)])
    );
  }
  return value;
}

function cloneData(value) {
  return JSON.parse(JSON.stringify(value));
}

function asLines(value) {
  return Array.isArray(value) ? value.join("\n") : value || "";
}

function fromLines(value) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseNumber(value, fallback = 0) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseOptionalNumber(value, fieldName = "", options = {}) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const parsed = Number.parseInt(text, 10);
  if (!Number.isFinite(parsed) || String(parsed) !== text) {
    throw new FormValidationError(t("messages.invalidNumberField").replace("{field}", fieldName || t("common.unknown")), fieldName);
  }
  if (options.min !== undefined && parsed < options.min) {
    throw new FormValidationError(
      t("messages.invalidMinNumberField").replace("{field}", fieldName || t("common.unknown")).replace("{min}", String(options.min)),
      fieldName
    );
  }
  if (options.max !== undefined && parsed > options.max) {
    throw new FormValidationError(
      t("messages.invalidMaxNumberField").replace("{field}", fieldName || t("common.unknown")).replace("{max}", String(options.max)),
      fieldName
    );
  }
  return parsed;
}

function parseOptionalFloat(value, fieldName = "", options = {}) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const parsed = Number.parseFloat(text);
  if (!Number.isFinite(parsed) || !/^-?\d+(\.\d+)?$/.test(text)) {
    throw new FormValidationError(t("messages.invalidNumberField").replace("{field}", fieldName || t("common.unknown")), fieldName);
  }
  if (options.min !== undefined && parsed < options.min) {
    throw new FormValidationError(
      t("messages.invalidMinNumberField").replace("{field}", fieldName || t("common.unknown")).replace("{min}", String(options.min)),
      fieldName
    );
  }
  if (options.max !== undefined && parsed > options.max) {
    throw new FormValidationError(
      t("messages.invalidMaxNumberField").replace("{field}", fieldName || t("common.unknown")).replace("{max}", String(options.max)),
      fieldName
    );
  }
  return parsed;
}

function parseOptionalBoolean(value) {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

function parseJson(value, fallback = {}) {
  if (!value.trim()) return fallback;
  return JSON.parse(value);
}

function fieldDisplayName(name) {
  const labels = {
    environment: t("fields.environment"),
    id: t("fields.id"),
    name: t("fields.name"),
    host_port: t("fields.hostPort"),
    matrix_external_peers: t("fields.externalPeers"),
    llm_profile: t("fields.llmProfile"),
    vision_profile: t("fields.visionProfile"),
    matrix_profile: t("fields.matrixProfile"),
    proactive_random_min_minutes: t("fields.proactiveRandomMinMinutes"),
    proactive_random_max_minutes: t("fields.proactiveRandomMaxMinutes"),
    proactive_poll_seconds: t("fields.proactivePollSeconds"),
    provider_family: t("fields.provider"),
    provider_alias: t("fields.providerAlias"),
    base_url: t("fields.baseUrl"),
    model: t("fields.model"),
    wire_api: t("fields.wireApi"),
    timeout_secs: t("fields.timeout"),
    temperature: t("fields.temperature"),
    max_tokens: t("fields.maxTokens"),
    extra_headers: t("fields.extraHeaders"),
    provider_extra: t("fields.providerExtra"),
    pricing: t("fields.pricing"),
    chat_template_kwargs: t("fields.chatTemplateKwargs"),
    tls_ca_cert_path: t("fields.tlsCaCertPath"),
    oauth_project: t("fields.oauthProject"),
    num_ctx: t("fields.numCtx"),
    num_predict: t("fields.numPredict"),
    temperature_override: t("fields.temperatureOverride"),
    max_images: t("fields.maxImages"),
    max_image_size_mb: t("fields.maxImageSizeMb"),
    max_image_turns: t("fields.maxImageTurns"),
    homeserver: t("fields.homeserver"),
    user_id: t("fields.matrixUser"),
    device_id: t("fields.deviceId"),
    access_token: t("fields.accessToken"),
    password: t("fields.password"),
    recovery_key: t("fields.recoveryKey"),
    stream_mode: t("fields.streamMode"),
    multi_message_delay_ms: t("fields.multiMessageDelayMs"),
    channel_debounce_ms: t("fields.channelDebounceMs"),
    draft_update_interval_ms: t("fields.draftUpdateIntervalMs"),
    approval_timeout_secs: t("fields.approvalTimeoutSecs"),
    reply_min_interval_secs: t("fields.replyMinIntervalSecs"),
    reply_queue_depth_max: t("fields.replyQueueDepthMax"),
    server_name: t("fields.serverName"),
    transport: t("fields.transport"),
    url: t("fields.url"),
    support_file_type: t("fields.supportFileType"),
    support_file_name: t("fields.supportFileName"),
    support_upload_file: t("fields.uploadFile"),
    template_file: t("fields.templateFile"),
    description: t("fields.description")
  };
  return labels[name] || name;
}

function readJsonField(data, key, fallback) {
  const raw = String(data.get(key) || "");
  if (!raw.trim()) return fallback;
  try {
    return JSON.parse(raw);
  } catch {
    throw new FormValidationError(t("messages.invalidJsonField").replace("{field}", fieldDisplayName(key)), key);
  }
}

function requireString(data, key) {
  const value = String(data.get(key) || "").trim();
  if (!value) {
    throw new FormValidationError(t("messages.requiredField").replace("{field}", fieldDisplayName(key)), key);
  }
  return value;
}

function requireNumber(data, key, options = {}) {
  const value = parseOptionalNumber(data.get(key), fieldDisplayName(key), options);
  if (value === undefined) {
    throw new FormValidationError(t("messages.requiredField").replace("{field}", fieldDisplayName(key)), key);
  }
  return value;
}

function requireLines(data, key) {
  const values = fromLines(String(data.get(key) || ""));
  if (!values.length) {
    throw new FormValidationError(t("messages.requiredField").replace("{field}", fieldDisplayName(key)), key);
  }
  return values;
}

function validateUrlLike(value, key, { required = false } = {}) {
  const text = String(value || "").trim();
  if (!text) {
    if (required) throw new FormValidationError(t("messages.requiredField").replace("{field}", fieldDisplayName(key)), key);
    return text;
  }
  try {
    const url = new URL(text);
    if (!["http:", "https:"].includes(url.protocol)) throw new Error("unsupported protocol");
  } catch {
    throw new FormValidationError(t("messages.invalidUrlField").replace("{field}", fieldDisplayName(key)), key);
  }
  return text;
}

function alertValidation(error) {
  return alertDialog(error.message || String(error));
}

function cleanEmptyValues(value) {
  if (Array.isArray(value)) return value.map(cleanEmptyValues);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .map(([key, child]) => [key, cleanEmptyValues(child)])
        .filter(([, child]) => child !== undefined && child !== "" && !(Array.isArray(child) && child.length === 0))
        .filter(([, child]) => !(child && typeof child === "object" && !Array.isArray(child) && Object.keys(child).length === 0))
    );
  }
  return value;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error?.message || response.statusText);
  }
  return payload.data ?? payload;
}

function setBusy(busy) {
  state.busy = busy;
  render();
}

function clearToast(kind = "all") {
  if (kind === "notice" || kind === "all") {
    if (noticeTimer) window.clearTimeout(noticeTimer);
    noticeTimer = null;
    state.notice = "";
    state.noticeKind = "";
  }
  if (kind === "error" || kind === "all") {
    if (errorTimer) window.clearTimeout(errorTimer);
    errorTimer = null;
    state.error = "";
  }
}

function showNotice(message, kind = "success") {
  clearToast("notice");
  state.notice = message || "";
  state.noticeKind = kind;
  if (state.notice) {
    noticeTimer = window.setTimeout(() => {
      clearToast("notice");
      render();
    }, 5000);
  }
}

function showError(message) {
  clearToast("error");
  state.error = message || "";
  if (state.error) {
    errorTimer = window.setTimeout(() => {
      clearToast("error");
      render();
    }, 20000);
  }
}

async function runAction(action, successKey) {
  try {
    setBusy(true);
    clearToast();
    const result = await action();
    if (successKey) showNotice(t(successKey));
    await refreshConfig(false);
    return result;
  } catch (error) {
    showError(error.message || String(error));
    return null;
  } finally {
    state.busy = false;
    render();
  }
}

function showDialog(options) {
  return new Promise((resolve) => {
    if (state.dialog) state.dialog.resolve(state.dialog.type === "prompt" ? null : false);
    const type = options.type || "alert";
    state.dialog = {
      type,
      title: options.title || "",
      message: options.message || "",
      confirmKey: options.confirmKey || (type === "alert" ? "actions.confirm" : "actions.confirm"),
      cancelKey: options.cancelKey || "actions.cancel",
      danger: options.danger === true,
      input: type === "prompt" ? String(options.defaultValue ?? "") : "",
      placeholder: options.placeholder || "",
      resolve
    };
    render();
    requestAnimationFrame(() => {
      const node = document.querySelector("[data-dialog-input]") || document.querySelector("[data-dialog-confirm]");
      node?.focus();
      if (node?.matches?.("[data-dialog-input]")) node.select?.();
    });
  });
}

function alertDialog(message, title = "") {
  return showDialog({ type: "alert", message, title });
}

function confirmDialog(message, { title = "", danger = true, confirmKey = "actions.confirm" } = {}) {
  return showDialog({ type: "confirm", message, title, danger, confirmKey });
}

function promptDialog(message, defaultValue = "", { title = "" } = {}) {
  return showDialog({ type: "prompt", message, defaultValue, title });
}

function settleDialog(result) {
  const dialog = state.dialog;
  if (!dialog) return;
  state.dialog = null;
  dialog.resolve(result);
  render();
}

async function refreshConfig(shouldRender = true) {
  state.config = await api("/api/config");
  state.selectedAgentId = selectedAgent() ? itemId(selectedAgent()) : "";
  state.selectedTemplateId = selectedTemplate() ? itemId(selectedTemplate()) : "";
  state.selectedSkillBundleId = selectedSkillBundle() ? itemId(selectedSkillBundle()) : "";
  state.selectedTemplateFile = selectedTemplate() ? selectedTemplateFile(selectedTemplate()) : "";
  if (shouldRender) render();
}

async function refreshSkillList(bundleId = state.selectedSkillBundleId) {
  if (!bundleId) return;
  const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills`);
  state.skillBundleSkills[bundleId] = result.skills || [];
  if (!state.selectedSkillName && state.skillBundleSkills[bundleId][0]) {
    state.selectedSkillName = state.skillBundleSkills[bundleId][0].name;
  }
}

async function refreshSkillDocument(bundleId = state.selectedSkillBundleId, skillName = state.selectedSkillName) {
  if (!bundleId || !skillName) return;
  const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}`);
  state.skillDocuments[`${bundleId}:${skillName}`] = result;
}

async function refreshAgentStatus(agentId) {
  const status = await api(`/api/agents/${encodeURIComponent(agentId)}/status`);
  state.agentStatuses[agentId] = status;
}

async function refreshAgentLogs(agentId) {
  const logs = await api(`/api/agents/${encodeURIComponent(agentId)}/logs?tail=${encodeURIComponent(state.logTail)}`);
  state.agentLogs[agentId] = logs;
}

async function refreshDashboard() {
  state.dashboard = await api("/api/dashboard");
  for (const row of state.dashboard.agents || []) {
    const id = itemId(row.agent);
    if (id) state.agentStatuses[id] = row.status;
  }
}

async function refreshDockerResources() {
  state.dockerResources = await api("/api/docker/resources");
}

async function refreshDockerImages() {
  state.dockerImages = await api("/api/docker/images");
}

function removeAgentLocalState(agentId) {
  state.config.agents = collection("agents").filter((agent) => itemId(agent) !== agentId);
  delete state.agentStatuses[agentId];
  delete state.agentLogs[agentId];
  if (state.dashboard?.agents) {
    state.dashboard.agents = state.dashboard.agents.filter((row) => itemId(row.agent) !== agentId);
  }
}

async function refreshDashboardInBackground() {
  state.dashboardRequested = true;
  const visible = state.selectedTab === "dashboard";
  state.dashboardLoading = visible;
  if (visible) render();
  try {
    await refreshDashboard();
    clearToast("error");
  } catch (error) {
    state.dashboardRequested = false;
    if (visible) showError(error.message || String(error));
  } finally {
    state.dashboardLoading = false;
    if (visible || state.selectedTab === "dashboard") render();
  }
}

async function refreshDockerResourcesInBackground() {
  state.dockerResourcesRequested = true;
  const visible = state.selectedTab === "resources";
  state.dockerResourcesLoading = visible;
  if (visible) render();
  try {
    await refreshDockerResources();
    clearToast("error");
  } catch (error) {
    state.dockerResourcesRequested = false;
    if (visible) showError(error.message || String(error));
  } finally {
    state.dockerResourcesLoading = false;
    if (visible || state.selectedTab === "resources") render();
  }
}

async function refreshDockerImagesInBackground() {
  state.dockerImagesRequested = true;
  const visible = state.selectedTab === "images";
  state.dockerImagesLoading = visible;
  if (visible) render();
  try {
    await refreshDockerImages();
    clearToast("error");
  } catch (error) {
    state.dockerImagesRequested = false;
    if (visible) showError(error.message || String(error));
  } finally {
    state.dockerImagesLoading = false;
    if (visible || state.selectedTab === "images") render();
  }
}

function optionList(items, selected, emptyKey) {
  const empty = emptyKey ? `<option value="">${escapeHtml(t(emptyKey))}</option>` : "";
  return `${empty}${items
    .map((item) => {
      const id = itemId(item);
      return `<option value="${escapeHtml(id)}" ${id === selected ? "selected" : ""}>${escapeHtml(id)}</option>`;
    })
    .join("")}`;
}

function agentProfileOptionList(kind, selected, emptyKey) {
  return `${optionList(collection(kind), selected, emptyKey)}<option value="${ADD_NEW_PROFILE_VALUE}">+ ${escapeHtml(t("actions.addNew"))}</option>`;
}

function profileUsage(kind, profileId) {
  const fieldName = `${kind}_profile`;
  return collection("agents")
    .filter((agent) => String(agent[fieldName] || "") === profileId)
    .map((agent) => ({ id: itemId(agent), fieldName }));
}

function profileUsageTag(kind, profileId) {
  if (!["llm", "vision", "matrix", "mcp"].includes(kind)) return "";
  const count = profileUsage(kind, profileId).length;
  const key = count ? "common.used" : "common.unused";
  return `<span class="list-tag usage-corner ${count ? "used" : "unused"}">${escapeHtml(t(key))}${count ? ` ${count}` : ""}</span>`;
}

function optionsFromPairs(items, selected) {
  return items
    .map(([value, label]) => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
}

function llmProviderOptions(selected) {
  return optionsFromPairs(
    Object.values(LLM_PRESETS).map((preset) => [preset.provider_family, preset.label]),
    selected
  );
}

function wireApiOptions(selected) {
  return optionsFromPairs(
    [
      ["chat_completions", "chat_completions"],
      ["responses", "responses"]
    ],
    selected
  );
}

function authModeOptions(selected) {
  return optionsFromPairs(
    [
      ["", t("common.none")],
      ["api_key", "api_key"],
      ["oauth", "oauth"]
    ],
    selected
  );
}

function booleanOptions(selected) {
  const value = selected === true ? "true" : selected === false ? "false" : "";
  return optionsFromPairs(
    [
      ["", t("common.none")],
      ["true", t("common.yes")],
      ["false", t("common.no")]
    ],
    value
  );
}

function streamModeOptions(selected) {
  return optionsFromPairs(
    [
      ["off", "off"],
      ["partial", "partial"],
      ["multi_message", "multi_message"]
    ],
    selected || "off"
  );
}

function templateFiles(template) {
  return template?.files && !Array.isArray(template.files) ? template.files : {};
}

function templateFileNames(template) {
  const files = templateFiles(template);
  const names = [...TEMPLATE_FILES];
  Object.keys(files).forEach((file) => {
    if (!names.includes(file)) names.push(file);
  });
  return names;
}

function aiFillTargetFiles(template) {
  return templateFileNames(template);
}

function aiFillReferenceFiles(template) {
  const names = templateFileNames(template);
  if (!state.aiFillReferenceFiles.length) return PROMPT_SYSTEM_FILES.filter((file) => names.includes(file));
  return state.aiFillReferenceFiles.filter((file) => names.includes(file));
}

function selectedTemplateFile(template) {
  const names = templateFileNames(template);
  return names.includes(state.selectedTemplateFile) ? state.selectedTemplateFile : names[0] || TEMPLATE_FILES[0];
}

function templateFileBadge(file) {
  const index = PROMPT_SYSTEM_FILES.indexOf(file);
  if (index >= 0) return `#${index + 1}`;
  if (file === "HEARTBEAT.md") return "HB";
  if (PROJECT_OPTIONAL_FILES.includes(file)) return "OPT";
  return "NEW";
}

function templateFileHelp(file) {
  if (PROMPT_SYSTEM_FILES.includes(file)) return t("prompts.officialFileHelp");
  if (file === "HEARTBEAT.md") return t("prompts.heartbeatFileHelp");
  if (PROJECT_OPTIONAL_FILES.includes(file)) return t("prompts.optionalServiceFileHelp");
  return t("prompts.customFileHelp");
}

function supportPathParts(path) {
  const text = String(path || "").replaceAll("\\", "/").replace(/^\/+/, "");
  const fallbackType = SKILL_SUPPORT_DIRS.includes(state.selectedSupportType) ? state.selectedSupportType : "references";
  const [type = fallbackType, ...rest] = text.split("/");
  return {
    type: SKILL_SUPPORT_DIRS.includes(type) ? type : fallbackType,
    filename: rest.join("/") || ""
  };
}

function supportFilePathFromParts(type, filename) {
  const normalizedType = String(type || state.selectedSupportType || "references").trim();
  const normalizedName = String(filename || "").trim().replaceAll("\\", "/").replace(/^\/+/, "");
  if (!SKILL_SUPPORT_DIRS.includes(normalizedType)) {
    throw new FormValidationError(t("messages.requiredField").replace("{field}", fieldDisplayName("support_file_type")), "support_file_type");
  }
  if (!normalizedName || normalizedName.includes("..") || normalizedName.endsWith("/") || !normalizedName.split("/").every(Boolean)) {
    throw new FormValidationError(t("messages.invalidSupportFileName"), "support_file_name");
  }
  const leaf = normalizedName.split("/").pop() || "";
  if (!leaf.includes(".") || leaf.startsWith(".") || leaf.endsWith(".")) {
    throw new FormValidationError(t("messages.invalidSupportFileName"), "support_file_name");
  }
  return `${normalizedType}/${normalizedName}`;
}

function supportFilePathFromForm(data) {
  const type = String(data.get("support_file_type") || state.selectedSupportType || "references").trim();
  const filename = String(data.get("support_file_name") || "").trim();
  return supportFilePathFromParts(type, filename);
}

function supportFileName(filePath) {
  const parts = supportPathParts(filePath);
  return parts.filename;
}

function supportFilesForType(doc, type = state.selectedSupportType) {
  return (doc?.files || []).filter((file) => supportPathParts(file).type === type);
}

function defaultSupportFileName(type = state.selectedSupportType) {
  if (type === "scripts") return "script.sh";
  if (type === "assets") return "asset.txt";
  return "notes.md";
}

function defaultSupportPath(type = state.selectedSupportType) {
  return `${type}/${defaultSupportFileName(type)}`;
}

function supportTypeLabel(type) {
  return t(`skills.supportTypes.${type}`);
}

function supportFileUploadPathFromForm(data, file) {
  const type = String(data.get("support_file_type") || state.selectedSupportType || "references").trim();
  const name = String(data.get("support_file_name") || file?.name || "").trim();
  return supportFilePathFromParts(type, name);
}

function renderTemplateAddFileControl() {
  if (!state.pendingTemplateFileName) {
    return `
      <button type="button" class="template-file-tab add" data-action="template-add-file">
        <span class="template-file-name">${escapeHtml(t("actions.addFile"))}</span>
        <small class="template-file-badge">+</small>
      </button>
    `;
  }
  return `
    <div class="template-file-new">
      <input
        type="text"
        value="${escapeHtml(state.pendingTemplateFileName)}"
        data-template-new-file
        aria-label="${escapeHtml(t("prompts.addFilePrompt"))}"
        autocomplete="off"
      />
      <button type="button" class="template-file-icon confirm" data-action="template-confirm-file" aria-label="${escapeHtml(t("actions.confirm"))}">✓</button>
      <button type="button" class="template-file-icon cancel" data-action="template-cancel-file" aria-label="${escapeHtml(t("actions.cancel"))}">×</button>
    </div>
  `;
}

function defaultTemplateFiles() {
  return cloneData(DEFAULT_TEMPLATE_FILES);
}

function nextAgentHostPort() {
  const used = new Set(collection("agents").map((agent) => Number(agent.host_port)).filter((port) => Number.isInteger(port)));
  let port = DEFAULT_AGENT_HOST_PORT;
  while (used.has(port) && port < 65535) port += 1;
  return port;
}

function defaultAgent(id) {
  return {
    id,
    host_port: nextAgentHostPort(),
    image: DEFAULT_ZEROCLAW_IMAGE,
    matrix: {},
    proactive: cloneData(DEFAULT_PROACTIVE),
    _draft: true
  };
}

function normalizeTemplateFilename(value) {
  const filename = String(value || "").trim();
  if (
    !filename ||
    filename.length > 128 ||
    filename.includes("..") ||
    filename.includes("/") ||
    filename.includes("\\") ||
    !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(filename)
  ) {
    throw new FormValidationError(t("messages.invalidTemplateFile"), "template_file");
  }
  return filename;
}

function updateTemplateDraftFromForm() {
  const template = selectedTemplate();
  const form = document.querySelector('[data-form="template"]');
  if (!template || !form) return;
  const data = readForm(form);
  const activeFile = selectedTemplateFile(template);
  template.id = String(data.get("id") || "").trim();
  template.description = String(data.get("description") || "");
  template.files = { ...templateFiles(template), [activeFile]: String(data.get(`file:${activeFile}`) || "") };
}

function syncAiFillDraftFromForm() {
  const form = document.querySelector('[data-form="template-ai-fill"]');
  if (!form) return;
  const data = readForm(form);
  state.aiFillProfile = String(data.get("llm_profile") || "");
  state.aiFillInstruction = String(data.get("instruction") || DEFAULT_AI_FILL_INSTRUCTION);
  state.aiFillDescription = String(data.get("description") || "");
  state.aiFillReferenceEnabled = data.get("use_references") === "on";
  state.aiFillReferenceFiles = data.getAll("reference_file").map((value) => String(value));
}

function renderAiFillPreservingScroll() {
  state.aiFillScrollTop = document.querySelector(".ai-fill-dialog")?.scrollTop || 0;
  render();
  requestAnimationFrame(() => {
    const dialog = document.querySelector(".ai-fill-dialog");
    if (dialog) dialog.scrollTop = state.aiFillScrollTop;
  });
}

function openAiFillDialog() {
  updateTemplateDraftFromForm();
  const llmProfiles = collection("llm");
  state.aiFillOpen = true;
  state.aiFillProfile = state.aiFillProfile || (llmProfiles[0] ? itemId(llmProfiles[0]) : "");
  state.aiFillInstruction = state.aiFillInstruction || DEFAULT_AI_FILL_INSTRUCTION;
  state.aiFillReferenceEnabled = false;
  state.aiFillReferenceFiles = [];
  render();
}

function openSupportFileDialog(kind) {
  state.supportFileDialog = {
    kind,
    type: state.selectedSupportType,
    name: kind === "upload" ? "" : defaultSupportFileName(state.selectedSupportType),
    content: ""
  };
  render();
}

function closeSupportFileDialog() {
  state.supportFileDialog = null;
  render();
}

async function runAiFill() {
  const template = selectedTemplate();
  const form = document.querySelector('[data-form="template-ai-fill"]');
  if (!template || !form) return;
  syncAiFillDraftFromForm();
  const targetFiles = aiFillTargetFiles(template);
  const references = state.aiFillReferenceEnabled ? aiFillReferenceFiles(template) : [];
  const payload = {
    llm_profile: requireString(readForm(form), "llm_profile"),
    instruction: state.aiFillInstruction,
    description: requireString(readForm(form), "description"),
    files: targetFiles,
    reference_files: references,
    current_files: Object.fromEntries(references.map((file) => [file, templateFiles(template)[file] || ""]))
  };
  try {
    setBusy(true);
    clearToast();
    const result = await api("/api/prompt-templates/ai-fill", { method: "POST", body: JSON.stringify(payload) });
    updateTemplateDraftFromForm();
    template.files = { ...templateFiles(template), ...(result.files || {}) };
    state.selectedTemplateFile = targetFiles[0] || state.selectedTemplateFile;
    state.aiFillOpen = false;
    showNotice(t("messages.aiFillGenerated"));
  } catch (error) {
    showError(error.message || String(error));
  } finally {
    state.busy = false;
    render();
  }
}

function llmFamily(item) {
  return item.provider_family || item.family || item.kind || "openai";
}

function createLlmProfile(id) {
  return { id, ...LLM_PRESETS.openai, _draft: true };
}

function createVisionProfile(id) {
  return {
    id,
    ...LLM_PRESETS.custom,
    provider_alias: "vision",
    model: "gpt-4o",
    max_images: 4,
    max_image_size_mb: 5,
    max_image_turns: 2,
    allow_remote_fetch: false,
    _draft: true
  };
}

function createProfileDraft(kind) {
  if (kind === "llm") return createLlmProfile(nextId(kind, collection(kind)));
  if (kind === "vision") return createVisionProfile(nextId("vision", collection(kind)));
  return { id: nextId(kind, collection(kind)), _draft: true };
}

function applyLlmPresetToEmptyFields(item, family) {
  const preset = LLM_PRESETS[family] || LLM_PRESETS.openai;
  const next = { ...item, provider_family: preset.provider_family };
  for (const key of LLM_PROVIDER_FIELDS) {
    if (key === "provider_family") continue;
    if (next[key] === undefined || next[key] === null || next[key] === "") next[key] = preset[key];
  }
  return next;
}

function isProviderVisible(item, families) {
  return families.includes(llmFamily(item));
}

function labelText(labelKey, attrs = "", helpKey = "") {
  const required = /\brequired\b/.test(attrs);
  const help = helpKey ? t(helpKey) : "";
  return `<span ${help ? `title="${escapeHtml(help)}"` : ""}>${escapeHtml(t(labelKey))}${required ? ' <b class="required-mark">*</b>' : ""}</span>`;
}

function helpText(helpKey) {
  return helpKey ? escapeHtml(t(helpKey)) : "";
}

function field(labelKey, name, value = "", attrs = "", helpKey = "") {
  const help = helpText(helpKey);
  const placeholder = help && !/\bplaceholder=/.test(attrs) ? `placeholder="${help}" title="${help}"` : "";
  return `<label class="field">${labelText(labelKey, attrs, helpKey)}<input name="${name}" value="${escapeHtml(
    value
  )}" ${attrs} ${placeholder} /></label>`;
}

function passwordField(labelKey, name, value = "", helpKey = "") {
  return field(labelKey, name, value ? "••••••••" : "", `type="password" autocomplete="new-password" data-secret="true"`, helpKey);
}

function textareaField(labelKey, name, value = "", attrs = "", helpKey = "") {
  const help = helpText(helpKey);
  const placeholder = help && !/\bplaceholder=/.test(attrs) ? `placeholder="${help}" title="${help}"` : "";
  return `<label class="field field-wide">${labelText(labelKey, attrs, helpKey)}<textarea name="${name}" ${attrs}>${escapeHtml(
    value
  )}</textarea></label>`.replace("<textarea", `<textarea ${placeholder}`);
}

function checkboxField(labelKey, name, checked = false, helpKey = "") {
  const help = helpKey ? t(helpKey) : "";
  return `<label class="check-field" ${help ? `title="${escapeHtml(help)}"` : ""}><input type="checkbox" name="${name}" ${checked ? "checked" : ""} /><span>${escapeHtml(
    t(labelKey)
  )}</span></label>`;
}

function shortHash(value) {
  return value ? String(value).slice(0, 12) : "";
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function selectField(labelKey, name, optionsHtml, attrs = "", helpKey = "") {
  const help = helpText(helpKey);
  return `<label class="field">${labelText(labelKey, attrs, helpKey)}<select name="${name}" ${attrs} ${help ? `title="${help}"` : ""}>${optionsHtml}</select></label>`;
}

const ACTION_ICONS = {
  "actions.applyTemplate": "file-check",
  "actions.archive": "archive",
  "actions.aiFill": "sparkles",
  "actions.cancel": "x",
  "actions.copyPath": "copy",
  "actions.create": "plus",
  "actions.delete": "trash",
  "actions.downloadLogs": "download",
  "actions.download": "download",
  "actions.duplicate": "copy",
  "actions.edit": "edit",
  "actions.export": "download",
  "actions.logs": "file-text",
  "actions.openFolder": "folder-open",
  "actions.refreshStatus": "refresh",
  "actions.removeFile": "trash",
  "actions.restart": "rotate",
  "actions.save": "save",
  "actions.start": "play",
  "actions.stop": "square",
  "actions.syncFromRuntime": "download",
  "actions.syncToRuntime": "upload",
  "actions.upload": "upload",
  "actions.validate": "circle-check",
  "actions.advancedActions": "chevron-up",
  "actions.collapseAdvancedActions": "chevron-down",
  "actions.resetMatrixState": "shield-alert",
  "actions.adopt": "badge-check",
  "actions.ignore": "eye-off",
  "actions.migrate": "arrow-right-left",
  "actions.clearDecision": "undo"
};

const ICON_PATHS = {
  archive: '<rect x="3" y="3" width="18" height="4" rx="1"></rect><path d="M5 7v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7"></path><path d="M10 12h4"></path>',
  "arrow-right-left": '<path d="M8 7h13"></path><path d="m18 4 3 3-3 3"></path><path d="M16 17H3"></path><path d="m6 14-3 3 3 3"></path>',
  "badge-check": '<path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.77 4 4 0 0 1 0 6.76 4 4 0 0 1-4.78 4.77 4 4 0 0 1-6.74 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"></path><path d="m9 12 2 2 4-4"></path>',
  check: '<path d="m5 12 4 4L19 6"></path>',
  "chevron-down": '<path d="m6 9 6 6 6-6"></path>',
  "chevron-up": '<path d="m18 15-6-6-6 6"></path>',
  "circle-check": '<circle cx="12" cy="12" r="10"></circle><path d="m9 12 2 2 4-4"></path>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><path d="M7 10l5 5 5-5"></path><path d="M12 15V3"></path>',
  edit: '<path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path>',
  "eye-off": '<path d="M10.7 5.1A10.9 10.9 0 0 1 12 5c7 0 10 7 10 7a13.2 13.2 0 0 1-2.2 3.3"></path><path d="M6.6 6.6C2.7 8.8 1 12 1 12s3 7 11 7a10.8 10.8 0 0 0 5.4-1.4"></path><path d="m2 2 20 20"></path><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"></path>',
  "file-check": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path><path d="M14 2v6h6"></path><path d="m9 15 2 2 4-4"></path>',
  "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path><path d="M14 2v6h6"></path><path d="M16 13H8"></path><path d="M16 17H8"></path><path d="M10 9H8"></path>',
  "folder-open": '<path d="M6 17h12a2 2 0 0 0 1.9-1.4l1.5-5A2 2 0 0 0 19.5 8H8.2a2 2 0 0 0-1.9 1.4L4 17V5a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v1"></path>',
  play: '<path d="m6 3 14 9-14 9Z"></path>',
  plus: '<path d="M12 5v14"></path><path d="M5 12h14"></path>',
  refresh: '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"></path><path d="M3 21v-5h5"></path><path d="M3 12A9 9 0 0 1 18.5 5.8L21 8"></path><path d="M21 3v5h-5"></path>',
  rotate: '<path d="M21 12a9 9 0 1 1-2.6-6.4"></path><path d="M21 3v6h-6"></path>',
  save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"></path><path d="M17 21v-8H7v8"></path><path d="M7 3v5h8"></path>',
  "shield-alert": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"></path><path d="M12 8v4"></path><path d="M12 16h.01"></path>',
  sparkles: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8Z"></path><path d="M5 3v4"></path><path d="M3 5h4"></path><path d="M19 17v4"></path><path d="M17 19h4"></path>',
  square: '<rect x="6" y="6" width="12" height="12" rx="2"></rect>',
  trash: '<path d="M3 6h18"></path><path d="M8 6V4h8v2"></path><path d="M19 6l-1 14H6L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path>',
  undo: '<path d="M9 14 4 9l5-5"></path><path d="M4 9h10a6 6 0 0 1 0 12h-4"></path>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><path d="M17 8l-5-5-5 5"></path><path d="M12 3v12"></path>',
  x: '<path d="M18 6 6 18"></path><path d="m6 6 12 12"></path>'
};

function actionButton(action, labelKey, variant = "secondary", disabled = false) {
  const label = t(labelKey);
  const icon = ACTION_ICONS[labelKey];
  const content = icon ? iconSvg(icon) : escapeHtml(label);
  const modeClass = icon ? "icon-button" : "text-button";
  return `<button type="button" class="button ${variant} ${modeClass}" data-action="${escapeHtml(action)}" title="${escapeHtml(label)}" aria-label="${escapeHtml(
    label
  )}" ${disabled ? "disabled" : ""}>${content}</button>`;
}

function iconSvg(name) {
  return `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24">${ICON_PATHS[name] || ""}</svg>`;
}

function render() {
  const app = document.querySelector("#app");
  app.innerHTML = `
    ${renderNotices()}
    <div class="layout">
      <nav class="side-nav" aria-label="${escapeHtml(t("nav.label"))}">
        ${TABS.map(
          (tab) =>
            `<button type="button" class="nav-item ${state.selectedTab === tab ? "active" : ""}" data-tab="${tab}">${escapeHtml(
              t(`nav.${tab}`)
            )}</button>`
        ).join("")}
      </nav>
      <section class="content-panel">${renderSelectedTab()}</section>
    </div>
    ${renderAiFillDialog()}
    ${renderResourceDeleteDialog()}
    ${renderSupportFileDialog()}
    ${renderDialog()}
  `;
}

function renderNotices() {
  const loading =
    state.busy ||
    (state.selectedTab === "dashboard" && state.dashboardLoading) ||
    (state.selectedTab === "images" && state.dockerImagesLoading) ||
    (state.selectedTab === "resources" && state.dockerResourcesLoading)
      ? renderNotice("muted", t("common.loading"), "status")
      : "";
  const notice = state.notice ? renderNotice(state.noticeKind || "success", state.notice, "status") : "";
  const error = state.error ? renderNotice("danger", state.error, "alert") : "";
  const notices = `${loading}${notice}${error}`;
  return notices ? `<div class="toast-region" aria-live="polite">${notices}</div>` : "";
}

function renderNotice(kind, message, role) {
  const duration = kind === "success" ? 5 : kind === "danger" ? 20 : 0;
  return `<div class="notice toast ${kind}" role="${role}">
    <span>${escapeHtml(message)}</span>
    <button type="button" class="toast-close" data-notice-dismiss title="${escapeHtml(t("actions.cancel"))}" aria-label="${escapeHtml(t("actions.cancel"))}">
      ${iconSvg("x")}
    </button>
    ${duration ? `<i class="toast-progress" style="animation-duration:${duration}s"></i>` : ""}
  </div>`;
}

function renderSelectedTab() {
  if (!state.config) return `<div class="empty-state">${escapeHtml(t("common.loading"))}</div>`;
  if (state.selectedTab === "dashboard") return renderDashboard();
  if (state.selectedTab === "images") return renderDockerImages();
  if (state.selectedTab === "resources") return renderDockerResources();
  if (state.selectedTab === "agents") return renderAgentEditor();
  if (state.selectedTab === "llm") return renderProfileManager("llm");
  if (state.selectedTab === "vision") return renderProfileManager("vision");
  if (state.selectedTab === "matrix") return renderProfileManager("matrix");
  if (state.selectedTab === "mcp") return renderProfileManager("mcp");
  if (state.selectedTab === "skills") return renderSkillsManager();
  if (state.selectedTab === "prompts") return renderPromptTemplates();
  if (state.selectedTab === "export") return renderExport();
  return "";
}

function renderDockerResources() {
  const audit = state.dockerResources;
  const expectedErrors = audit?.expected?.errors || [];
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("resources.title"))}</h2><p>${escapeHtml(t("resources.subtitle"))}</p></div>
      <div class="button-row">
        ${actionButton("refresh-docker-resources", "actions.refreshStatus")}
      </div>
    </header>
    <details class="info-panel">
      <summary>${escapeHtml(t("resources.aboutTitle"))}<small>${escapeHtml(t("resources.aboutSummary"))}</small></summary>
      <dl class="data-list compact">
        ${renderDetail(t("resources.expected"), t("resources.expectedHelp"))}
        ${renderDetail(t("resources.conflicts"), t("resources.conflictsHelp"))}
        ${renderDetail(t("resources.orphans"), t("resources.orphansHelp"))}
        ${renderDetail(t("resources.untracked"), t("resources.untrackedHelp"))}
        ${renderDetail(t("resources.adopted"), t("resources.reviewedHelp"))}
      </dl>
    </details>
    <div class="resource-summary">
      ${renderResourceSummaryMetric("resources.containers", audit?.containers)}
      ${renderResourceSummaryMetric("resources.volumes", audit?.volumes)}
      ${renderResourceSummaryMetric("resources.networks", audit?.networks)}
    </div>
    ${
      expectedErrors.length
        ? `<section class="result-box warning"><strong>${escapeHtml(t("resources.expectedErrors"))}</strong><pre>${escapeHtml(
            JSON.stringify(expectedErrors, null, 2)
          )}</pre></section>`
        : ""
    }
    ${renderResourceGroup("resources.containers", audit?.containers, "container")}
    ${renderResourceGroup("resources.volumes", audit?.volumes, "volume")}
    ${renderResourceGroup("resources.networks", audit?.networks, "network")}
  `;
}

function renderDockerImages() {
  const inventory = state.dockerImages;
  const images = inventory?.images || [];
  const recommended = inventory?.recommended || { official: DEFAULT_ZEROCLAW_IMAGE, python: "zeroclaw-python:v0.8.1-debian", root: "zeroclaw-root:v0.8.1-debian" };
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("images.title"))}</h2><p>${escapeHtml(t("images.subtitle"))}</p></div>
      <div class="button-row">
        ${actionButton("refresh-docker-images", "actions.refreshStatus")}
      </div>
    </header>
    <section class="form-section">
      <div class="button-row">
        ${actionButton("image-pull-official", "actions.pullOfficial")}
        ${actionButton("image-build-python", "actions.buildPythonImage")}
        ${actionButton("image-build-root", "actions.buildRootImage", "danger")}
      </div>
      <p class="muted-text">${escapeHtml(t("images.buildHint"))}</p>
    </section>
    <div class="resource-summary">
      ${renderImageMetric(t("images.official"), recommended.official, imageByReference(images, recommended.official))}
      ${renderImageMetric(t("images.python"), recommended.python, imageByReference(images, recommended.python))}
      ${renderImageMetric(t("images.root"), recommended.root, imageByReference(images, recommended.root))}
    </div>
    <section class="resource-group">
      <h3>${escapeHtml(t("images.localImages"))}</h3>
      <div class="resource-list">
        ${images.length ? images.map(renderImageRow).join("") : `<div class="empty-state">${escapeHtml(t("common.empty"))}</div>`}
      </div>
    </section>
  `;
}

function imageByReference(images, reference) {
  return images.find((image) => image.reference === reference);
}

function renderImageMetric(label, reference, image) {
  return `<div class="metric">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(image?.present ? t("images.present") : t("images.missing"))}</strong>
    <small>${escapeHtml(reference || "")}</small>
  </div>`;
}

function renderImageRow(image) {
  return `<article class="resource-row">
    <div>
      <strong>${escapeHtml(image.reference || t("common.unnamed"))}</strong>
      <span>${escapeHtml(t(`imageKinds.${image.kind}`) || image.kind || "custom")}</span>
    </div>
    <div>${renderDetail(t("images.present"), image.present ? t("common.yes") : t("common.no"))}${renderDetail(t("images.shortId"), image.short_id || "")}</div>
    <div>${renderDetail(t("images.user"), image.user || "")}${renderDetail(t("images.size"), formatBytes(image.size))}</div>
    <details class="agent-detail-panel">
      <summary>${escapeHtml(t("resources.labels"))}</summary>
      <pre>${escapeHtml(JSON.stringify({ repo_tags: image.repo_tags || [], labels: image.labels || {}, error: image.error || null }, null, 2))}</pre>
    </details>
  </article>`;
}

function renderResourceSummaryMetric(labelKey, group) {
  const counts = resourceCounts(group);
  return `<div class="metric">
    <span>${escapeHtml(t(labelKey))}</span>
    <strong>${escapeHtml(
      t("resources.summary")
        .replace("{expected}", String(counts.expected))
        .replace("{orphans}", String(counts.orphans))
        .replace("{legacy}", String(counts.legacy))
        .replace("{conflicts}", String(counts.conflicts))
    )}</strong>
  </div>`;
}

function resourceCounts(group) {
  return {
    expected: (group?.expected || []).length,
    orphans: (group?.orphans || []).length,
    legacy: (group?.legacy || []).length,
    conflicts: (group?.conflicts || []).length,
    ignored: (group?.ignored || []).length,
    adopted: (group?.adopted || []).length
  };
}

function renderResourceGroup(titleKey, group, kind) {
  if (!group) return `<section class="resource-panel"><h3>${escapeHtml(t(titleKey))}</h3><div class="empty-state">${escapeHtml(t("common.loading"))}</div></section>`;
  return `<section class="resource-panel">
    <h3>${escapeHtml(t(titleKey))}</h3>
    ${renderResourceBucket("resources.expected", group.expected, kind, "expected")}
    ${renderResourceBucket("resources.conflicts", group.conflicts, kind, "conflicts")}
    ${renderResourceBucket("resources.orphans", group.orphans, kind, "orphans")}
    ${renderResourceBucket("resources.untracked", group.legacy, kind, "legacy")}
    ${renderResourceBucket("resources.adopted", group.adopted, kind, "adopted")}
    ${renderResourceBucket("resources.ignored", group.ignored, kind, "ignored")}
  </section>`;
}

function renderResourceBucket(titleKey, rows = [], kind, bucket) {
  return `<details class="info-panel resource-bucket" ${bucket === "conflicts" && rows.length ? "open" : ""}>
    <summary>${escapeHtml(t(titleKey))}<small>${escapeHtml(
      t("resources.count").replace("{count}", String(rows.length))
    )}</small></summary>
    ${
      rows.length
        ? `<div class="resource-table">${rows.map((row) => renderResourceRow(row, kind, bucket)).join("")}</div>`
        : `<div class="empty-state">${escapeHtml(t("resources.emptyBucket"))}</div>`
    }
  </details>`;
}

function renderResourceRow(row, kind, bucket) {
  const labels = row.labels || {};
  const state = resourceClassificationLabel(row.state || row.status || row.classification || "");
  return `<article class="resource-row resource-${bucket}">
    <div>
      <strong>${escapeHtml(row.name || shortHash(row.id) || t("common.unnamed"))}</strong>
      <span>${escapeHtml(resourceClassificationLabel(row.classification || ""))}</span>
    </div>
    <div>${renderDetail(t("resources.kindLabel"), resourceKindLabel(kind))}${renderDetail(t("resources.role"), resourceRoleLabel(row.role || ""))}</div>
    <div>${renderDetail(t("resources.agent"), row.agent_id || row.agent_name || "")}${renderDetail(t("resources.state"), state)}</div>
    <details class="agent-detail-panel">
      <summary>${escapeHtml(t("resources.labels"))}</summary>
      ${renderResourceLabels(labels)}
    </details>
    ${renderResourceActions(row, kind, bucket)}
  </article>`;
}

function resourceKindLabel(kind) {
  return t(`resourceKinds.${kind}`) || kind;
}

function resourceRoleLabel(role) {
  return role ? t(`resourceRoles.${role}`) || role : "";
}

function resourceClassificationLabel(classification) {
  return classification ? t(`resourceClassifications.${classification}`) || classification : "";
}

function renderResourceActions(row, kind, bucket) {
  const name = row.name || "";
  if (!name || bucket === "expected") return "";
  const encoded = encodeURIComponent(`${kind}:${name}`);
  const actions = [];
  if (["conflicts", "legacy", "orphans"].includes(bucket)) {
    actions.push(actionButton(`resource-adopt:${encoded}`, "actions.adopt"));
    actions.push(actionButton(`resource-ignore:${encoded}`, "actions.ignore"));
  }
  if (["adopted", "ignored"].includes(bucket)) {
    actions.push(actionButton(`resource-clear:${encoded}`, "actions.clearDecision"));
  }
  if (kind === "volume" && ["conflicts", "legacy", "orphans", "adopted", "ignored"].includes(bucket)) {
    actions.push(actionButton(`resource-migrate:${encoded}`, "actions.migrate"));
  }
  if (["legacy", "orphans", "ignored"].includes(bucket)) {
    actions.push(actionButton(`resource-delete:${encoded}`, "actions.delete", "danger"));
  }
  return actions.length ? `<div class="button-row resource-actions">${actions.join("")}</div>` : "";
}

function renderResourceLabels(labels) {
  const entries = Object.entries(labels || {}).filter(([key]) => key.startsWith("zeroclaw.") || key.startsWith("com.docker.compose."));
  if (!entries.length) return `<div class="empty-state compact">${escapeHtml(t("common.none"))}</div>`;
  return `<dl class="label-list">${entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value))}</dd></div>`)
    .join("")}</dl>`;
}

function renderResourceDeleteDialog() {
  const pending = state.pendingResourceDelete;
  if (!pending) return "";
  const matches = state.pendingResourceDeleteInput === pending.name;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal-panel resource-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="resource-delete-title">
        <header class="modal-header">
          <div>
            <h3 id="resource-delete-title">${escapeHtml(t("resources.deleteTitle"))}</h3>
            <p>${escapeHtml(t(`resourceDeleteWarnings.${pending.kind}`) || t("resourceDeleteWarnings.default"))}</p>
          </div>
          <button type="button" class="button icon-button" data-action="resource-delete-cancel" aria-label="${escapeHtml(t("actions.cancel"))}">${iconSvg("x")}</button>
        </header>
        <dl class="data-list compact">
          ${renderDetail(t("resources.kindLabel"), resourceKindLabel(pending.kind))}
          ${renderDetail(t("resources.name"), pending.name)}
          ${renderDetail(t("resources.classificationLabel"), resourceClassificationLabel(pending.classification || ""))}
        </dl>
        <label class="field">
          <span>${escapeHtml(t("resources.deleteTypeName"))}</span>
          <input data-resource-delete-input value="${escapeHtml(state.pendingResourceDeleteInput)}" autocomplete="off" />
        </label>
        <footer class="button-row modal-actions">
          ${actionButton("resource-delete-cancel", "actions.cancel")}
          ${actionButton("resource-delete-confirm", "actions.delete", "danger", !matches)}
        </footer>
      </section>
    </div>`;
}

function renderSupportFileDialog() {
  const dialog = state.supportFileDialog;
  if (!dialog) return "";
  const isUpload = dialog.kind === "upload";
  const titleKey = isUpload ? "skills.uploadFileTitle" : "skills.addTextFileTitle";
  const subtitleKey = isUpload ? "skills.uploadFileSubtitle" : "skills.addTextFileSubtitle";
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal-panel support-file-dialog" role="dialog" aria-modal="true" aria-labelledby="support-file-dialog-title">
        <header class="modal-header">
          <div>
            <h3 id="support-file-dialog-title">${escapeHtml(t(titleKey))}</h3>
            <p>${escapeHtml(t(subtitleKey))}</p>
          </div>
          ${actionButton("support-file-dialog-close", "actions.cancel", "secondary")}
        </header>
        <form class="form-grid" data-form="support-file-dialog">
          ${selectField(
            "fields.supportFileType",
            "support_file_type",
            SKILL_SUPPORT_DIRS.map((type) => `<option value="${type}" ${dialog.type === type ? "selected" : ""}>${escapeHtml(supportTypeLabel(type))}</option>`).join(""),
            "",
            "fieldHelp.skills.supportFileType"
          )}
          ${field("fields.supportFileName", "support_file_name", dialog.name || "", "", "fieldHelp.skills.supportFileName")}
          ${
            isUpload
              ? `<label class="field field-wide">
                  <span>${escapeHtml(t("fields.uploadFile"))}</span>
                  <input type="file" name="support_upload_file" />
                </label>
                <div class="notice muted field-wide">${escapeHtml(t("skills.uploadTextOnlyNotice"))}</div>`
              : textareaField("fields.supportFileContent", "support_file_content", dialog.content || "", "", "fieldHelp.skills.supportFileContent")
          }
        </form>
        <footer class="button-row modal-actions">
          ${actionButton("support-file-dialog-close", "actions.cancel", "secondary")}
          ${actionButton(isUpload ? "support-file-upload-save" : "support-file-create-save", isUpload ? "actions.upload" : "actions.create", "primary")}
        </footer>
      </section>
    </div>`;
}

function renderDialog() {
  const dialog = state.dialog;
  if (!dialog) return "";
  const isPrompt = dialog.type === "prompt";
  const isAlert = dialog.type === "alert";
  const confirmVariant = dialog.danger ? "danger" : "primary";
  return `
    <div class="modal-backdrop" role="presentation" data-dialog-backdrop>
      <section class="modal-panel app-dialog" role="${isAlert ? "alertdialog" : "dialog"}" aria-modal="true" aria-labelledby="app-dialog-title">
        <header class="modal-header">
          <div>
            <h3 id="app-dialog-title">${escapeHtml(dialog.title || t(`dialog.${dialog.type}Title`))}</h3>
          </div>
        </header>
        <p class="app-dialog-message">${escapeHtml(dialog.message)}</p>
        ${
          isPrompt
            ? `<label class="field field-wide">
                <input data-dialog-input value="${escapeHtml(dialog.input)}" placeholder="${escapeHtml(dialog.placeholder)}" autocomplete="off" />
              </label>`
            : ""
        }
        <footer class="button-row modal-actions">
          ${isAlert ? "" : `<button type="button" class="button secondary text-button" data-dialog-cancel>${escapeHtml(t(dialog.cancelKey))}</button>`}
          <button type="button" class="button ${confirmVariant} text-button" data-dialog-confirm>${escapeHtml(t(dialog.confirmKey))}</button>
        </footer>
      </section>
    </div>`;
}

function renderDashboard() {
  const rows = state.dashboard?.agents || [];
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("dashboard.title"))}</h2><p>${escapeHtml(t("dashboard.subtitle"))}</p></div>
      <div class="button-row">
        <label class="inline-control"><span>${escapeHtml(t("dashboard.tail"))}</span><input name="log-tail" type="number" min="1" max="2000" value="${escapeHtml(
          state.logTail
        )}" data-log-tail /></label>
        <label class="check-field inline-check"><input type="checkbox" data-auto-refresh ${state.autoRefresh ? "checked" : ""} /><span>${escapeHtml(
          t("dashboard.autoRefresh")
        )}</span></label>
        ${actionButton("refresh-all-status", "actions.refreshStatus")}
      </div>
    </header>
    <div class="agent-grid">
      ${
        rows.length
          ? rows.map((row) => renderAgentCard(row.agent)).join("")
          : `<div class="empty-state">${escapeHtml(t("dashboard.empty"))}</div>`
      }
    </div>
    ${renderHistory()}
  `;
}

function renderAgentCard(agent) {
  const id = itemId(agent);
  const status = state.agentStatuses[id];
  const logs = state.agentLogs[id];
  const normalizedState = status?.normalized_state || status?.state || "unknown";
  const model = agent.model?.model || agent.llm_profile || t("common.none");
  const mappedPort = status?.mapped_port || (agent.host_port ? `127.0.0.1:${agent.host_port}` : "");
  const hasLogs = Boolean(logs);
  return `
    <article class="agent-card state-card state-${escapeHtml(normalizedState)}">
      <header class="card-header">
        <div>
          <h3>${escapeHtml(id || t("common.unnamed"))}</h3>
          <p>${escapeHtml(agent.enabled === false ? t("common.disabled") : t("common.enabled"))}</p>
        </div>
        <span class="status-pill state-${escapeHtml(normalizedState)}">${escapeHtml(normalizedState || t("common.unknown"))}</span>
      </header>
      <div class="agent-card-summary">
        ${renderMetric(t("fields.hostPort"), agent.host_port || t("common.none"))}
        ${renderMetric(t("observability.mappedPort"), mappedPort || t("common.none"))}
        ${renderMetric(t("fields.model"), model)}
        ${renderMetric(t("fields.matrixProfile"), agent.matrix_profile || t("common.none"))}
      </div>
      <div class="agent-card-meta">
        <span class="${status?.needs_rebuild ? "meta-flag warning" : "meta-flag"}">${escapeHtml(
          `${t("observability.rebuild")}: ${status?.needs_rebuild ? t("common.yes") : t("common.no")}`
        )}</span>
        <span class="meta-flag">${escapeHtml(`${t("observability.started")}: ${formatDate(status?.started_at) || t("common.unknown")}`)}</span>
        <span class="meta-flag">${escapeHtml(`${t("fields.mcpStatus")}: ${agent.mcp_profile || t("common.none")}`)}</span>
      </div>
      <div class="button-row card-actions">
        ${actionButton(`agent-start:${id}`, "actions.start", "primary")}
        ${actionButton(`agent-stop:${id}`, "actions.stop")}
        ${actionButton(`agent-restart:${id}`, "actions.restart")}
        ${actionButton(`agent-logs:${id}`, "actions.logs")}
        ${actionButton(`agent-download-logs:${id}`, "actions.downloadLogs")}
        ${actionButton(`agent-edit:${id}`, "actions.edit")}
        ${actionButton(`agent-delete:${id}`, "actions.delete", "danger")}
      </div>
      <details class="agent-detail-panel">
        <summary>${escapeHtml(t("fields.advanced"))}</summary>
        <dl class="data-list compact">
          ${renderDetail(t("observability.containerId"), shortHash(status?.container_id))}
          ${renderDetail(t("observability.image"), status?.image || agent.image || "")}
          ${renderDetail(t("observability.created"), formatDate(status?.created_at))}
          ${renderDetail(t("observability.health"), status?.health_status || "")}
          ${renderDetail(t("observability.restartCount"), status?.restart_count ?? "")}
          ${renderDetail(t("observability.configHash"), shortHash(status?.config_hash))}
          ${renderDetail(t("observability.containerHash"), shortHash(status?.container_config_hash))}
          ${renderDetail(t("observability.latestExport"), formatDate(status?.latest_export_time))}
        </dl>
      </details>
      ${
        hasLogs
          ? `<details class="agent-detail-panel log-panel" open><summary>${escapeHtml(t("actions.logs"))}</summary><pre class="log-viewer">${escapeHtml(
              formatLogs(logs, status)
            )}</pre></details>`
          : ""
      }
    </article>
  `;
}

function renderMetric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(displayValue(value))}</strong></div>`;
}

function renderDetail(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(displayValue(value))}</dd></div>`;
}

function displayValue(value) {
  return value === undefined || value === null || value === "" ? t("common.none") : value;
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return t("common.none");
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function renderHistory() {
  const history = state.dashboard?.history || [];
  return `<section class="history-panel">
    <header class="section-header compact"><div><h3>${escapeHtml(t("history.title"))}</h3><p>${escapeHtml(
      t("history.subtitle")
    )}</p></div></header>
    ${
      history.length
        ? `<div class="history-list">${history
            .map(
              (entry) => `<div class="history-row">
                <span>${escapeHtml(formatDate(entry.timestamp))}</span>
                <strong>${escapeHtml(entry.operation || "")}</strong>
                <span>${escapeHtml(entry.agent_id || t("common.none"))}</span>
                <span>${escapeHtml(entry.status || "")}</span>
              </div>`
            )
            .join("")}</div>`
        : `<div class="empty-state">${escapeHtml(t("history.empty"))}</div>`
    }
  </section>`;
}

function formatLogs(logs, status) {
  if (logs?.lines?.length) return logs.lines.join("\n");
  if (logs?.details?.message) return logs.details.message;
  if (status?.details?.message) return status.details.message;
  return t("dashboard.logsEmpty");
}

function renderAgentEditor() {
  const agent = selectedAgent();
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("agents.title"))}</h2><p>${escapeHtml(t("agents.subtitle"))}</p></div>
    </header>
    <div class="split">
      ${renderListPanel(
        "agents",
        collection("agents"),
        state.selectedAgentId,
        `${actionButton("agent-new", "actions.create", "primary")}
         ${actionButton("agent-duplicate", "actions.duplicate", "secondary", !agent)}
         ${actionButton("agent-delete-current", "actions.delete", "danger", !agent)}`
      )}
      <form class="form-panel" data-form="agent">${agent ? renderAgentForm(agent) : renderEmptyEditor("agents.empty")}</form>
    </div>
  `;
}

function renderListPanel(kind, items, selectedId, actionsHtml = "") {
  return `<aside class="list-panel">
    ${actionsHtml ? `<div class="list-panel-actions">${actionsHtml}</div>` : ""}
    <div class="list-panel-items">${renderItemList(kind, items, selectedId)}</div>
  </aside>`;
}

function renderItemList(kind, items, selectedId) {
  if (!items.length) return `<div class="empty-state">${escapeHtml(t("common.empty"))}</div>`;
  return items
    .map((item) => {
      const id = itemId(item);
      const modelTag = kind === "llm" && item.model ? `<span class="list-tag">${escapeHtml(item.model)}</span>` : "";
      const usedTag = profileUsageTag(kind, id);
      return `<button type="button" class="list-item ${id === selectedId ? "active" : ""}" data-select-${kind}="${escapeHtml(
        id
      )}"><span class="list-item-main">${escapeHtml(id)}</span>${modelTag}${usedTag}</button>`;
    })
    .join("");
}

function renderAgentForm(agent) {
  return `
    ${renderAgentPrimaryFields(agent)}
    ${renderAgentProactiveFields(agent)}
    ${renderAgentAdvancedFields(agent)}
    <div class="button-row form-actions">
      ${actionButton("agent-save", "actions.save", "primary")}
      ${actionButton("agent-validate", "actions.validate")}
      ${actionButton("agent-apply-template", "actions.applyTemplate", "secondary", !agent.prompt_template)}
      ${renderAgentAdvancedActions()}
    </div>
    ${renderValidation()}
  `;
}

function renderAgentAdvancedActions() {
  return `<div class="advanced-action-cluster ${state.agentAdvancedActionsOpen ? "open" : ""}">
    <div class="advanced-action-popover" aria-hidden="${state.agentAdvancedActionsOpen ? "false" : "true"}">
      ${actionButton("agent-sync-to-runtime", "actions.syncToRuntime")}
      ${actionButton("agent-sync-from-runtime", "actions.syncFromRuntime")}
      ${actionButton("agent-reset-matrix-state", "actions.resetMatrixState", "danger")}
    </div>
    ${actionButton(
      "agent-advanced-actions-toggle",
      state.agentAdvancedActionsOpen ? "actions.collapseAdvancedActions" : "actions.advancedActions"
    )}
  </div>`;
}

function renderAgentPrimaryFields(agent) {
  const hostPort = agent.host_port || DEFAULT_AGENT_HOST_PORT;
  const matrix = agent.matrix || {};
  return `<section class="form-section">
    <div class="form-grid">
      ${field("fields.id", "id", itemId(agent), "required", "fieldHelp.agent.id")}
      ${field("fields.hostPort", "host_port", hostPort, 'type="number" min="1" max="65535" required', "fieldHelp.agent.hostPort")}
      ${selectField("fields.llmProfile", "llm_profile", agentProfileOptionList("llm", agent.llm_profile, "common.none"), "required data-agent-profile-kind=\"llm\"", "fieldHelp.agent.llmProfile")}
      ${selectField("fields.visionProfile", "vision_profile", agentProfileOptionList("vision", agent.vision_profile, "common.none"), 'data-agent-profile-kind="vision"', "fieldHelp.agent.visionProfile")}
      ${selectField(
        "fields.matrixProfile",
        "matrix_profile",
        agentProfileOptionList("matrix", agent.matrix_profile, "common.none"),
        'required data-agent-profile-kind="matrix"',
        "fieldHelp.agent.matrixProfile"
      )}
      ${selectField(
        "fields.promptTemplate",
        "prompt_template",
        optionList(collection("prompt_templates"), agent.prompt_template, "common.none"),
        "",
        "fieldHelp.agent.promptTemplate"
      )}
      ${selectField("fields.mcpProfile", "mcp_profile", agentProfileOptionList("mcp", agent.mcp_profile, "common.none"), 'data-agent-profile-kind="mcp"', "fieldHelp.agent.mcpProfile")}
      ${textareaField("fields.skillBundles", "skill_bundles", asLines(agent.skill_bundles), "", "fieldHelp.agent.skillBundles")}
      ${textareaField("fields.externalPeers", "matrix_external_peers", asLines(matrix.external_peers), "required", "fieldHelp.agent.externalPeers")}
    </div>
  </section>`;
}

function renderAgentAdvancedFields(agent) {
  return `<details class="form-section">
    <summary>${escapeHtml(t("fields.advanced"))}</summary>
    <div class="form-grid">
      ${selectField("fields.imagePreset", "image_preset", imageOptions(agent.image || DEFAULT_ZEROCLAW_IMAGE), 'data-image-preset', "fieldHelp.agent.image")}
      ${field("fields.dockerImage", "image", agent.image || DEFAULT_ZEROCLAW_IMAGE, 'data-image-input', "fieldHelp.agent.image")}
      ${selectField(
        "fields.templateApplyMode",
        "template_apply_mode",
        ["keep", "missing", "overwrite"]
          .map(
            (mode) =>
              `<option value="${mode}" ${agent.template_apply_mode === mode ? "selected" : ""}>${escapeHtml(
                t(`templateApply.${mode}`)
              )}</option>`
          )
          .join(""),
        "",
        "fieldHelp.agent.templateApplyMode"
      )}
      ${textareaField("fields.environment", "environment", JSON.stringify(agent.environment || {}, null, 2), "", "fieldHelp.agent.environment")}
    </div>
  </details>`;
}

function imageOptions(selected) {
  const inventory = state.dockerImages;
  const recommended = inventory?.recommended || { official: DEFAULT_ZEROCLAW_IMAGE, python: "zeroclaw-python:v0.8.1-debian", root: "zeroclaw-root:v0.8.1-debian" };
  const rows = [
    [recommended.official, t("images.official")],
    [recommended.python, t("images.python")],
    [recommended.root, t("images.root")]
  ];
  for (const image of inventory?.images || []) {
    if (image.reference && !rows.some(([value]) => value === image.reference)) rows.push([image.reference, image.reference]);
  }
  if (selected && !rows.some(([value]) => value === selected)) rows.push([selected, selected]);
  rows.push(["__custom__", t("images.custom")]);
  return rows
    .map(([value, label]) => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)} (${escapeHtml(value)})</option>`)
    .join("");
}

function renderAgentProactiveFields(agent) {
  const proactive = { ...DEFAULT_PROACTIVE, ...(agent.proactive || {}) };
  return `<details class="form-section" ${proactive.enabled === true ? "open" : ""}>
    <summary>${escapeHtml(t("fields.proactiveSettings"))}</summary>
    <div class="form-grid">
      ${checkboxField("fields.proactiveEnabled", "proactive_enabled", proactive.enabled === true, "fieldHelp.agent.proactiveEnabled")}
      ${field("fields.proactiveTarget", "proactive_target", proactive.target || "", "", "fieldHelp.agent.proactiveTarget")}
      ${field("fields.proactiveRandomMinMinutes", "proactive_random_min_minutes", proactive.random_min_minutes ?? "", 'type="number" min="1"', "fieldHelp.agent.proactiveRandomMinMinutes")}
      ${field("fields.proactiveRandomMaxMinutes", "proactive_random_max_minutes", proactive.random_max_minutes ?? "", 'type="number" min="1"', "fieldHelp.agent.proactiveRandomMaxMinutes")}
      ${field("fields.proactivePollSeconds", "proactive_poll_seconds", proactive.poll_seconds ?? "", 'type="number" min="30"', "fieldHelp.agent.proactivePollSeconds")}
      ${field("fields.proactiveQuietHours", "proactive_quiet_hours", proactive.quiet_hours || "", "", "fieldHelp.agent.proactiveQuietHours")}
      ${field("fields.proactiveTimezone", "proactive_timezone", proactive.timezone || "", "", "fieldHelp.agent.proactiveTimezone")}
      ${field("fields.proactiveChannel", "proactive_channel", proactive.channel || "", "", "fieldHelp.agent.proactiveChannel")}
      ${field("fields.proactiveAgentUrl", "proactive_agent_url", proactive.agent_url || "", 'type="url"', "fieldHelp.agent.proactiveAgentUrl")}
      ${textareaField("fields.proactivePrompt", "proactive_prompt", proactive.prompt || "", "", "fieldHelp.agent.proactivePrompt")}
    </div>
  </details>`;
}

function renderValidation() {
  if (!state.validationResult) return "";
  const errors = state.validationResult.errors || [];
  const warnings = state.validationResult.warnings || [];
  if (!errors.length && !warnings.length) return "";
  const kind = errors.length ? "danger" : warnings.length ? "warning" : "success";
  return `<div class="result-box ${kind}">
    <strong>${escapeHtml(state.validationResult.valid ? t("validation.valid") : t("validation.invalid"))}</strong>
    ${[...errors, ...warnings].map((item) => `<p>${escapeHtml(item.field)}: ${escapeHtml(item.message)}</p>`).join("")}
  </div>`;
}

function renderProfileManager(kind) {
  const items = collection(kind);
  const selectedId = state[`selected${kind}Id`] || itemId(items[0]);
  const selected = items.find((item) => itemId(item) === selectedId) || items[0] || null;
  state[`selected${kind}Id`] = selected ? itemId(selected) : "";
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t(`${kind}.title`))}</h2><p>${escapeHtml(t(`${kind}.subtitle`))}</p></div>
    </header>
    <div class="split">
      ${renderListPanel(
        kind,
        items,
        state[`selected${kind}Id`],
        `${actionButton(`${kind}-new`, "actions.create", "primary")}
         ${actionButton(`${kind}-delete-current`, "actions.delete", "danger", !selected)}`
      )}
      <form class="form-panel" data-form="${kind}">${selected ? renderProfileForm(kind, selected) : renderEmptyEditor(`${kind}.empty`)}</form>
    </div>
  `;
}

function renderProfileForm(kind, item) {
  const usage = renderProfileUsage(kind, itemId(item));
  if (kind === "vision") {
    const profile = applyLlmPresetToEmptyFields(item, llmFamily(item));
    return `
      ${usage}
      <div class="form-grid">
        ${field("fields.id", "id", itemId(item), "required")}
        ${selectField("fields.provider", "provider_family", llmProviderOptions(profile.provider_family || "custom"), 'required data-llm-provider="true"', "fieldHelp.vision.provider")}
        ${field("fields.providerAlias", "provider_alias", profile.provider_alias || profile.alias || "vision", "required", "fieldHelp.vision.providerAlias")}
        ${field("fields.baseUrl", "base_url", profile.base_url || "", "required", "fieldHelp.vision.baseUrl")}
        ${field("fields.model", "model", profile.model || "", "required", "fieldHelp.vision.model")}
        ${selectField("fields.wireApi", "wire_api", wireApiOptions(profile.wire_api || "chat_completions"), "required", "fieldHelp.vision.wireApi")}
        ${field("fields.timeout", "timeout_secs", profile.timeout_secs ?? 120, 'type="number" min="1" required', "fieldHelp.vision.timeout")}
        ${passwordField("fields.apiKey", "api_key", profile.api_key || "", "fieldHelp.vision.apiKey")}
      </div>
      <details class="advanced-panel">
        <summary>${escapeHtml(t("fields.multimodalLimits"))}</summary>
        <div class="form-grid">
          ${field("fields.maxImages", "max_images", profile.max_images ?? 4, 'type="number" min="1" max="16"', "fieldHelp.vision.maxImages")}
          ${field("fields.maxImageSizeMb", "max_image_size_mb", profile.max_image_size_mb ?? 5, 'type="number" min="1" max="20"', "fieldHelp.vision.maxImageSizeMb")}
          ${field("fields.maxImageTurns", "max_image_turns", profile.max_image_turns ?? 2, 'type="number" min="0"', "fieldHelp.vision.maxImageTurns")}
          ${checkboxField("fields.allowRemoteFetch", "allow_remote_fetch", profile.allow_remote_fetch === true, "fieldHelp.vision.allowRemoteFetch")}
        </div>
      </details>
      <div class="button-row form-actions">${actionButton("profile-save", "actions.save", "primary")}</div>
    `;
  }
  if (kind === "llm") {
    const profile = applyLlmPresetToEmptyFields(item, llmFamily(item));
    const family = llmFamily(profile);
    return `
      ${usage}
      <div class="form-grid">
        ${field("fields.id", "id", itemId(item), "required")}
        ${selectField("fields.provider", "provider_family", llmProviderOptions(family), 'required data-llm-provider="true"')}
        ${field("fields.providerAlias", "provider_alias", profile.provider_alias || profile.alias || "", "required")}
        ${field("fields.baseUrl", "base_url", profile.base_url || "", family === "custom" ? "required" : "")}
        ${field("fields.model", "model", profile.model || "", "required")}
        ${selectField("fields.wireApi", "wire_api", wireApiOptions(profile.wire_api || "chat_completions"), "required")}
        ${field("fields.timeout", "timeout_secs", profile.timeout_secs || profile.timeout || "", 'type="number" min="1" required')}
        ${passwordField("fields.apiKey", "api_key", profile.api_key || "")}
      </div>
      ${renderLlmAdvancedFields(profile)}
      <div class="button-row form-actions">${actionButton("profile-save", "actions.save", "primary")}</div>
    `;
  }
  if (kind === "matrix") {
    return `
      ${usage}
      <div class="form-grid">
        ${field("fields.id", "id", itemId(item), "required", "fieldHelp.matrix.id")}
        ${field("fields.homeserver", "homeserver", item.homeserver || "", "required", "fieldHelp.matrix.homeserver")}
        ${field("fields.matrixUser", "user_id", item.user_id || "", "", "fieldHelp.matrix.userId")}
        ${field("fields.deviceId", "device_id", item.device_id || "", "", "fieldHelp.matrix.deviceId")}
        ${passwordField("fields.password", "password", item.password || "", "fieldHelp.matrix.password")}
        ${passwordField("fields.recoveryKey", "recovery_key", item.recovery_key || "", "fieldHelp.matrix.recoveryKey")}
        ${textareaField("fields.allowedRooms", "allowed_rooms", asLines(item.allowed_rooms), "", "fieldHelp.matrix.allowedRooms")}
      </div>
      ${renderMatrixBehaviorFields(item)}
      ${renderMatrixAdvancedFields(item)}
      <div class="button-row form-actions">${actionButton("profile-save", "actions.save", "primary")}</div>
    `;
  }
  return `
    ${usage}
    <div class="form-grid">
      ${field("fields.id", "id", itemId(item), "required")}
      ${field("fields.serverName", "server_name", item.server_name || "")}
      ${field("fields.transport", "transport", item.transport || "http")}
      ${field("fields.url", "url", item.url || "")}
      ${passwordField("fields.token", "token", item.token || "")}
      ${field("fields.timeout", "timeout_secs", item.timeout_secs || "", 'type="number" min="1"')}
      ${checkboxField("fields.deferredLoading", "deferred_loading", item.deferred_loading === true)}
    </div>
    <div class="button-row form-actions">${actionButton("profile-save", "actions.save", "primary")}</div>
  `;
}

function renderProfileUsage(kind, profileId) {
  if (!["llm", "vision", "matrix", "mcp"].includes(kind)) return "";
  const users = profileUsage(kind, profileId);
  const statusKey = users.length ? "common.used" : "common.unused";
  const fieldLabelKeys = {
    llm_profile: "fields.llmProfile",
    vision_profile: "fields.visionProfile",
    matrix_profile: "fields.matrixProfile",
    mcp_profile: "fields.mcpProfile"
  };
  const body = users.length
    ? `<div class="profile-usage-list">${users
        .map(
          (user) =>
            `<button type="button" class="profile-usage-agent" data-action="agent-edit:${escapeHtml(user.id)}">${escapeHtml(user.id)}<span>${escapeHtml(
              t(fieldLabelKeys[user.fieldName] || "") || user.fieldName
            )}</span></button>`
        )
        .join("")}</div>`
    : `<p>${escapeHtml(t("profiles.noUsage"))}</p>`;
  return `<section class="profile-usage">
    <div class="profile-usage-header">
      <strong>${escapeHtml(t("profiles.usedBy"))}</strong>
      <span class="list-tag ${users.length ? "used" : "unused"}">${escapeHtml(t(statusKey))}${users.length ? ` ${users.length}` : ""}</span>
    </div>
    ${body}
  </section>`;
}

function createProfileFromAgentSelect(select) {
  const kind = select?.dataset?.agentProfileKind;
  if (!["llm", "vision", "matrix", "mcp"].includes(kind)) return;
  const agent = selectedAgent();
  const previousValue = agent ? String(agent[`${kind}_profile`] || "") : "";
  select.value = previousValue;
  const form = select.form;
  if (form && agent) {
    try {
      const draft = agentFromForm(form);
      const index = state.config.agents.findIndex((item) => itemId(item) === state.selectedAgentId);
      if (index >= 0) state.config.agents[index] = { ...state.config.agents[index], ...draft };
    } catch (_error) {
      // Incomplete agent drafts should not block quick profile creation.
    }
  }
  const item = createProfileDraft(kind);
  state.config.profiles[kind].unshift(item);
  state[`selected${kind}Id`] = item.id;
  state.selectedTab = kind;
  try {
    localStorage.setItem("zeroclaw.webui.selectedTab", kind);
  } catch (_error) {
    // Tab persistence is best effort.
  }
  clearToast();
  render();
  queueMicrotask(() => document.querySelector(`[data-form="${kind}"] [name="id"]`)?.select());
}

function renderMatrixBehaviorFields(item) {
  return `
    <details class="advanced-panel" open>
      <summary>${escapeHtml(t("fields.matrixBehavior"))}</summary>
      <div class="form-grid">
        ${checkboxField("fields.mentionOnly", "mention_only", item.mention_only === true, "fieldHelp.matrix.mentionOnly")}
        ${checkboxField("fields.replyInThread", "reply_in_thread", item.reply_in_thread === true, "fieldHelp.matrix.replyInThread")}
        ${checkboxField("fields.ackReactions", "ack_reactions", item.ack_reactions !== false, "fieldHelp.matrix.ackReactions")}
        ${checkboxField(
          "fields.interruptOnNewMessage",
          "interrupt_on_new_message",
          item.interrupt_on_new_message === true,
          "fieldHelp.matrix.interruptOnNewMessage"
        )}
        ${selectField("fields.streamMode", "stream_mode", streamModeOptions(item.stream_mode || "multi_message"), "", "fieldHelp.matrix.streamMode")}
        ${passwordField("fields.accessToken", "access_token", item.access_token || "", "fieldHelp.matrix.accessToken")}
        ${field(
          "fields.multiMessageDelayMs",
          "multi_message_delay_ms",
          item.multi_message_delay_ms ?? 800,
          'type="number" min="0"',
          "fieldHelp.matrix.multiMessageDelayMs"
        )}
        ${field("fields.channelDebounceMs", "channel_debounce_ms", item.channel_debounce_ms ?? 0, 'type="number" min="0"', "fieldHelp.matrix.channelDebounceMs")}
      </div>
    </details>
  `;
}

function renderMatrixAdvancedFields(item) {
  return `
    <details class="advanced-panel">
      <summary>${escapeHtml(t("fields.advanced"))}</summary>
      <div class="form-grid">
        ${field(
          "fields.draftUpdateIntervalMs",
          "draft_update_interval_ms",
          item.draft_update_interval_ms ?? "",
          'type="number" min="50"',
          "fieldHelp.matrix.draftUpdateIntervalMs"
        )}
        ${field("fields.approvalTimeoutSecs", "approval_timeout_secs", item.approval_timeout_secs ?? "", 'type="number" min="1"', "fieldHelp.matrix.approvalTimeoutSecs")}
        ${textareaField("fields.excludedTools", "excluded_tools", asLines(item.excluded_tools), "", "fieldHelp.matrix.excludedTools")}
        ${field("fields.replyMinIntervalSecs", "reply_min_interval_secs", item.reply_min_interval_secs ?? "", 'type="number" min="0"', "fieldHelp.matrix.replyMinIntervalSecs")}
        ${field("fields.replyQueueDepthMax", "reply_queue_depth_max", item.reply_queue_depth_max ?? "", 'type="number" min="0"', "fieldHelp.matrix.replyQueueDepthMax")}
        ${field("fields.hostIp", "host_ip", item.host_ip || "", "", "fieldHelp.matrix.hostIp")}
      </div>
    </details>
  `;
}

function renderLlmAdvancedFields(item) {
  const family = llmFamily(item);
  return `
    <details class="advanced-panel">
      <summary>${escapeHtml(t("fields.advanced"))}</summary>
      <div class="form-grid">
        ${field("fields.kind", "kind", item.kind || "")}
        ${field("fields.temperature", "temperature", item.temperature ?? "", 'type="number" step="0.01" min="0" max="2"')}
        ${field("fields.maxTokens", "max_tokens", item.max_tokens ?? "", 'type="number" min="1"')}
        ${checkboxField("fields.requiresOpenaiAuth", "requires_openai_auth", item.requires_openai_auth === true)}
        ${textareaField("fields.fallback", "fallback", asLines(item.fallback))}
        ${textareaField("fields.fallbackModels", "fallback_models", asLines(item.fallback_models))}
        ${textareaField("fields.extraHeaders", "extra_headers", JSON.stringify(item.extra_headers || {}, null, 2))}
        ${checkboxField("fields.mergeSystemIntoUser", "merge_system_into_user", item.merge_system_into_user === true)}
        ${textareaField("fields.providerExtra", "provider_extra", JSON.stringify(item.provider_extra || {}, null, 2))}
        ${textareaField("fields.pricing", "pricing", JSON.stringify(item.pricing || {}, null, 2))}
        ${selectField("fields.nativeTools", "native_tools", booleanOptions(item.native_tools))}
        ${selectField("fields.think", "think", booleanOptions(item.think))}
        ${textareaField("fields.chatTemplateKwargs", "chat_template_kwargs", JSON.stringify(item.chat_template_kwargs || {}, null, 2))}
        ${field("fields.tlsCaCertPath", "tls_ca_cert_path", item.tls_ca_cert_path || "")}
        ${
          isProviderVisible(item, ["gemini"])
            ? `${selectField("fields.authMode", "auth_mode", authModeOptions(item.auth_mode || ""))}
               ${passwordField("fields.oauthClientId", "oauth_client_id", item.oauth_client_id || "")}
               ${passwordField("fields.oauthClientSecret", "oauth_client_secret", item.oauth_client_secret || "")}
               ${field("fields.oauthProject", "oauth_project", item.oauth_project || "")}`
            : ""
        }
        ${
          isProviderVisible(item, ["ollama"])
            ? `${field("fields.numCtx", "num_ctx", item.num_ctx ?? "", 'type="number" min="1"')}
               ${field("fields.numPredict", "num_predict", item.num_predict ?? "", 'type="number"')}
               ${field("fields.temperatureOverride", "temperature_override", item.temperature_override ?? "", 'type="number" step="0.01" min="0" max="2"')}`
            : ""
        }
      </div>
    </details>
  `;
}

function renderSkillsManager() {
  const bundle = selectedSkillBundle();
  if (bundle && !state.skillBundleSkills[itemId(bundle)] && !state.busy) {
    queueMicrotask(() => refreshSkillList(itemId(bundle)).then(() => render()).catch((error) => showError(error.message || String(error))));
  }
  const skill = selectedSkill();
  if (bundle && skill && !selectedSkillDoc() && !state.busy) {
    queueMicrotask(() => refreshSkillDocument(itemId(bundle), skill.name).then(() => render()).catch((error) => showError(error.message || String(error))));
  }
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("skills.title"))}</h2><p>${escapeHtml(t("skills.subtitle"))}</p></div>
    </header>
    ${renderSkillsViewTabs()}
    ${renderSelectedSkillsView()}
  `;
}

function renderSkillsViewTabs() {
  return `
    <div class="sub-tabs" role="tablist" aria-label="${escapeHtml(t("skills.tabsLabel"))}">
      ${SKILLS_VIEWS.map(
        (view) => `
          <button
            type="button"
            class="sub-tab ${state.selectedSkillsView === view ? "active" : ""}"
            data-skills-view="${escapeHtml(view)}"
            role="tab"
            aria-selected="${state.selectedSkillsView === view ? "true" : "false"}"
          >${escapeHtml(t(`skills.tabs.${view}`))}</button>
        `
      ).join("")}
    </div>
  `;
}

function renderSelectedSkillsView() {
  if (!SKILLS_VIEWS.includes(state.selectedSkillsView)) state.selectedSkillsView = "bundles";
  if (state.selectedSkillsView === "bundles") return renderSkillBundlesView();
  if (state.selectedSkillsView === "support") return renderSkillSupportView();
  if (state.selectedSkillsView === "runtime") return renderSkillRuntimeSettingsView();
  return renderSkillLibraryView();
}

function renderSkillRuntimeSettingsView() {
  return `
    <form class="form-panel" data-form="skills-settings">
      <section class="form-section">
        <div class="section-header compact">
          <div><h3>${escapeHtml(t("skills.settings"))}</h3><p>${escapeHtml(t("skills.runtimeHelp"))}</p></div>
        </div>
        <div class="form-grid">
          ${checkboxField("fields.allowScripts", "allow_scripts", state.config.skills?.allow_scripts === true, "fieldHelp.skills.allowScripts")}
          ${checkboxField("fields.openSkillsEnabled", "open_skills_enabled", state.config.skills?.open_skills_enabled === true, "fieldHelp.skills.openSkillsEnabled")}
          ${selectField("fields.promptInjectionMode", "prompt_injection_mode", ["full", "compact"].map((mode) => `<option value="${mode}" ${state.config.skills?.prompt_injection_mode === mode ? "selected" : ""}>${escapeHtml(mode)}</option>`).join(""), "", "fieldHelp.skills.promptInjectionMode")}
          ${field("fields.registryUrl", "registry_url", state.config.skills?.registry_url || "https://github.com/zeroclaw-labs/zeroclaw-skills", 'type="url"', "fieldHelp.skills.registryUrl")}
          ${textareaField("fields.extraRegistries", "extra_registries", JSON.stringify(state.config.skills?.extra_registries || [], null, 2), "", "fieldHelp.skills.extraRegistries")}
          ${checkboxField("fields.skillCreationEnabled", "skill_creation_enabled", state.config.skills?.skill_creation?.enabled === true, "fieldHelp.skills.skillCreationEnabled")}
          ${field("fields.skillCreationMaxSkills", "skill_creation_max_skills", state.config.skills?.skill_creation?.max_skills ?? 500, 'type="number" min="1"', "fieldHelp.skills.skillCreationMaxSkills")}
          ${field("fields.skillCreationSimilarity", "skill_creation_similarity_threshold", state.config.skills?.skill_creation?.similarity_threshold ?? 0.85, 'type="number" min="0" max="1" step="0.01"', "fieldHelp.skills.skillCreationSimilarity")}
          ${checkboxField("fields.installSuggestionsEnabled", "install_suggestions_enabled", state.config.skills?.install_suggestions?.enabled === true, "fieldHelp.skills.installSuggestionsEnabled")}
          ${checkboxField("fields.skillImprovementEnabled", "skill_improvement_enabled", state.config.skills?.skill_improvement?.enabled === true, "fieldHelp.skills.skillImprovementEnabled")}
          ${field("fields.skillImprovementCooldown", "skill_improvement_cooldown_secs", state.config.skills?.skill_improvement?.cooldown_secs ?? 3600, 'type="number" min="0"', "fieldHelp.skills.skillImprovementCooldown")}
          ${field("fields.skillImprovementNudge", "skill_improvement_nudge_interval_iterations", state.config.skills?.skill_improvement?.nudge_interval_iterations ?? 10, 'type="number" min="0"', "fieldHelp.skills.skillImprovementNudge")}
          ${field("fields.skillImprovementMaxReview", "skill_improvement_max_review_iterations", state.config.skills?.skill_improvement?.max_review_iterations ?? 8, 'type="number" min="1"', "fieldHelp.skills.skillImprovementMaxReview")}
        </div>
        <div class="button-row form-actions">${actionButton("skills-settings-save", "actions.save", "primary")}</div>
      </section>
    </form>
  `;
}

function renderSkillLibraryView() {
  const bundle = selectedSkillBundle();
  const doc = selectedSkillDoc();
  return `
    <div class="split">
      ${renderListPanel(
        "skill-bundles",
        skillBundles(),
        state.selectedSkillBundleId
      )}
      <div class="form-panel">
        ${bundle ? renderSkillListAndEditor(bundle, doc) : renderEmptyEditor("skills.empty")}
      </div>
    </div>
  `;
}

function renderSkillBundlesView() {
  const bundle = selectedSkillBundle();
  return `
    <div class="split">
      ${renderListPanel(
        "skill-bundles",
        skillBundles(),
        state.selectedSkillBundleId,
        `${actionButton("skill-bundle-new", "actions.create", "primary")}
         ${actionButton("skill-bundle-delete-current", "actions.delete", "danger", !bundle)}`
      )}
      <div class="form-panel">
        ${bundle ? renderSkillBundleSettings(bundle) : renderEmptyEditor("skills.empty")}
      </div>
    </div>
  `;
}

function renderSkillBundleSettings(bundle) {
  const bundleId = itemId(bundle);
  return `
    <form data-form="skill-bundle">
      <section class="form-section">
        <div class="section-header compact">
          <div><h3>${escapeHtml(t("skills.bundleSettings"))}</h3><p>${escapeHtml(t("skills.bundleSettingsHelp"))}</p></div>
        </div>
        <div class="form-grid">
          ${field("fields.id", "id", bundleId, "required", "fieldHelp.skills.bundleId")}
          ${field("fields.directory", "directory", bundle.directory || `shared/skills/${bundleId}`, "", "fieldHelp.skills.bundleDirectory")}
          ${textareaField("fields.includeSkills", "include", asLines(bundle.include), "", "fieldHelp.skills.includeSkills")}
          ${textareaField("fields.excludeSkills", "exclude", asLines(bundle.exclude), "", "fieldHelp.skills.excludeSkills")}
        </div>
        <div class="button-row form-actions">
          ${actionButton(`skill-bundle-open-folder:${bundleId}`, "actions.openFolder", "secondary")}
          ${actionButton(`skill-bundle-copy-path:${bundleId}`, "actions.copyPath", "secondary")}
          ${actionButton("skill-bundle-save", "actions.save", "primary")}
        </div>
      </section>
    </form>
  `;
}

function renderSkillListAndEditor(bundle, doc) {
  const bundleId = itemId(bundle);
  const skills = state.skillBundleSkills[bundleId] || [];
  return `
    <section class="form-section">
      <header class="section-header compact">
        <div><h3>${escapeHtml(t("skills.bundleSkills"))}</h3><p>${escapeHtml(t("skills.bundleSkillsHelp"))}</p></div>
        <div class="button-row">
          ${actionButton(`skill-open-folder:${bundleId}:${state.selectedSkillName || ""}`, "actions.openFolder", "secondary", !selectedSkill())}
          ${actionButton(`skill-copy-path:${bundleId}:${state.selectedSkillName || ""}`, "actions.copyPath", "secondary", !selectedSkill())}
          ${actionButton("skill-refresh", "actions.refreshStatus")}
          ${actionButton("skill-new-toggle", "actions.create", "primary")}
        </div>
      </header>
      ${state.skillNewOpen ? renderSkillCreateForm() : ""}
      <div class="template-file-tabs">
        ${
          skills.length
            ? skills
                .map((skill) => `<button type="button" class="file-tab ${skill.name === state.selectedSkillName ? "active" : ""}" data-skill-name="${escapeHtml(skill.name)}">${escapeHtml(skill.name)}</button>`)
                .join("")
            : `<div class="empty-state compact">${escapeHtml(t("skills.noSkills"))}</div>`
        }
      </div>
      ${doc ? renderSkillDocumentEditor(doc) : ""}
    </section>
  `;
}

function renderSkillCreateForm() {
  return `<form class="nested-form" data-form="skill-create">
    <div class="form-grid">
      ${field("fields.name", "name", "", "required", "fieldHelp.skills.skillName")}
      ${field("fields.version", "version", "0.1.0", "", "fieldHelp.skills.version")}
      ${textareaField("fields.description", "description", "", "required", "fieldHelp.skills.description")}
      ${textareaField("fields.tags", "tags", "", "", "fieldHelp.skills.tags")}
    </div>
    <div class="button-row form-actions">
      ${actionButton("skill-create", "actions.create", "primary")}
      ${actionButton("skill-new-toggle", "actions.cancel")}
    </div>
  </form>`;
}

function renderSkillDocumentEditor(doc) {
  return `<form data-form="skill-doc">
    <div class="form-grid">
      ${field("fields.name", "name", doc.frontmatter?.name || doc.name || "", "required", "fieldHelp.skills.skillName")}
      ${field("fields.version", "version", doc.frontmatter?.version || "0.1.0", "", "fieldHelp.skills.version")}
      ${field("fields.author", "author", doc.frontmatter?.author || "", "", "fieldHelp.skills.author")}
      ${field("fields.license", "license", doc.frontmatter?.license || "", "", "fieldHelp.skills.license")}
      ${field("fields.category", "category", doc.frontmatter?.category || "", "", "fieldHelp.skills.category")}
      ${textareaField("fields.description", "description", doc.frontmatter?.description || "", "required", "fieldHelp.skills.description")}
      ${textareaField("fields.tags", "tags", asLines(doc.frontmatter?.tags), "", "fieldHelp.skills.tags")}
      ${textareaField("fields.skillBody", "body", doc.body || "", "", "fieldHelp.skills.body")}
    </div>
    <div class="button-row form-actions">
      ${actionButton("skill-save", "actions.save", "primary")}
      ${actionButton("skill-archive", "actions.archive", "danger")}
    </div>
  </form>`;
}

function renderSkillSupportView() {
  const bundle = selectedSkillBundle();
  const skill = selectedSkill();
  const doc = selectedSkillDoc();
  for (const row of skillBundles()) {
    const bundleId = itemId(row);
    if (bundleId && !state.skillBundleSkills[bundleId] && !state.busy) {
      queueMicrotask(() => refreshSkillList(bundleId).then(() => render()).catch((error) => showError(error.message || String(error))));
    }
  }
  if (!bundle) return renderEmptyEditor("skills.empty");
  if (!skill) return renderEmptyEditor("skills.noSkills");
  if (!doc) return renderEmptyEditor("skills.loadingSkill");
  if (!SKILL_SUPPORT_DIRS.includes(state.selectedSupportType)) state.selectedSupportType = "references";
  const files = supportFilesForType(doc);
  const selectedFile = files.includes(state.selectedSkillFile) ? state.selectedSkillFile : files[0] || "";
  if (selectedFile && selectedFile !== state.selectedSkillFile && !state.busy) {
    queueMicrotask(() => loadSkillSupportFile(selectedFile));
  }
  const path = state.skillFilePathDraft || selectedFile || defaultSupportPath();
  const pathParts = supportPathParts(path);
  return `
    <section class="form-section">
      <header class="section-header compact">
        <div>
          <h3>${escapeHtml(t("skills.supportFiles"))}</h3>
          <p>${escapeHtml(itemId(bundle))} / ${escapeHtml(skill.name)} · ${escapeHtml(t("skills.supportFilesHelp"))}</p>
        </div>
      </header>
      <form class="form-panel" data-form="skill-doc">
        <div class="support-file-layout">
          ${renderSupportSkillTree()}
          <div class="support-file-workspace">
            ${renderSupportTypeTabs(doc)}
            ${state.selectedSupportType === "scripts" ? renderScriptsGate() : ""}
            <div class="support-file-toolbar">
              <div>
                <strong>${escapeHtml(supportTypeLabel(state.selectedSupportType))}</strong>
                <span>${escapeHtml(t("skills.supportTypeHelp"))}</span>
              </div>
              <div class="button-row">
                ${actionButton("support-file-create-open", "actions.addFile", "secondary")}
                ${actionButton("support-file-upload-open", "actions.upload", "secondary")}
              </div>
            </div>
            <div class="support-file-browser">
              <aside class="support-file-list compact-list">
                ${
                  files.length
                    ? files
                        .map(
                          (file) => `
                            <button
                              type="button"
                              class="list-item ${file === selectedFile ? "active" : ""}"
                              data-skill-file="${escapeHtml(file)}"
                            ><span class="list-item-main">${escapeHtml(supportFileName(file))}</span></button>
                          `
                        )
                        .join("")
                    : `<div class="empty-state compact">${escapeHtml(t("skills.noSupportFiles"))}</div>`
                }
              </aside>
              <div class="form-grid">
                <input type="hidden" name="support_file_type" value="${escapeHtml(pathParts.type)}" />
                ${field("fields.supportFileName", "support_file_name", pathParts.filename || defaultSupportFileName(), "", "fieldHelp.skills.supportFileName")}
                ${textareaField("fields.supportFileContent", "support_file_content", state.skillFileDraft || "", "", "fieldHelp.skills.supportFileContent")}
              </div>
            </div>
          </div>
        </div>
        <div class="button-row form-actions">
          ${actionButton("skill-file-load", "actions.load")}
          ${actionButton("skill-file-save", "actions.save", "primary")}
          ${actionButton("skill-file-download", "actions.download", "secondary", !selectedFile)}
          ${actionButton("skill-file-delete", "actions.delete", "danger")}
        </div>
      </form>
    </section>
  `;
}

function renderSupportTypeTabs(doc) {
  return `
    <div class="sub-tabs compact" role="tablist" aria-label="${escapeHtml(t("skills.supportTypeTabsLabel"))}">
      ${SKILL_SUPPORT_DIRS.map((type) => {
        const count = supportFilesForType(doc, type).length;
        return `
          <button
            type="button"
            class="sub-tab ${state.selectedSupportType === type ? "active" : ""}"
            data-support-type="${escapeHtml(type)}"
            role="tab"
            aria-selected="${state.selectedSupportType === type ? "true" : "false"}"
          >${escapeHtml(supportTypeLabel(type))} <span class="tab-count">${count}</span></button>
        `;
      }).join("")}
    </div>
  `;
}

function renderScriptsGate() {
  if (state.config.skills?.allow_scripts === true) {
    return `<div class="notice success compact-notice">${escapeHtml(t("skills.scriptsEnabledNotice"))}</div>`;
  }
  return `
    <div class="notice danger compact-notice">
      <span>${escapeHtml(t("skills.scriptsDisabledNotice"))}</span>
      ${actionButton("skills-enable-scripts", "actions.enable", "primary")}
    </div>
  `;
}

function renderSupportSkillTree() {
  const selectedBundleId = itemId(selectedSkillBundle());
  return `
    <aside class="support-file-list">
      ${skillBundles()
        .map((bundle) => {
          const bundleId = itemId(bundle);
          const open = bundleId === selectedBundleId;
          const skills = state.skillBundleSkills[bundleId] || [];
          return `
            <details class="skill-tree-bundle" ${open ? "open" : ""}>
              <summary>${escapeHtml(bundleId)}</summary>
              <div class="skill-tree-items">
                ${
                  skills.length
                    ? skills
                        .map(
                          (row) => `
                            <button
                              type="button"
                              class="list-item ${bundleId === selectedBundleId && row.name === state.selectedSkillName ? "active" : ""}"
                              data-support-skill-bundle="${escapeHtml(bundleId)}"
                              data-support-skill-name="${escapeHtml(row.name)}"
                            ><span class="list-item-main">${escapeHtml(row.name)}</span></button>
                          `
                        )
                        .join("")
                    : `<div class="empty-state compact">${escapeHtml(t("skills.noSkills"))}</div>`
                }
              </div>
            </details>
          `;
        })
        .join("")}
    </aside>
  `;
}

function renderPromptTemplates() {
  const template = selectedTemplate();
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("prompts.title"))}</h2><p>${escapeHtml(t("prompts.subtitle"))}</p></div>
    </header>
    <details class="info-panel prompt-order">
      <summary>
        <span>${escapeHtml(t("prompts.orderTitle"))}</span>
        <small>${escapeHtml(t("prompts.orderSummary"))}</small>
      </summary>
      <p>${escapeHtml(t("prompts.orderSystem"))}</p>
      <pre>${escapeHtml(t("prompts.orderFlow"))}</pre>
      <p>${escapeHtml(t("prompts.customNote"))}</p>
    </details>
    <div class="split wide">
      ${renderListPanel(
        "templates",
        collection("prompt_templates"),
        state.selectedTemplateId,
        `${actionButton("template-new", "actions.create", "primary")}
         ${actionButton("template-duplicate", "actions.duplicate", "secondary", !template)}
         ${actionButton("template-delete-current", "actions.delete", "danger", !template)}`
      )}
      <form class="form-panel" data-form="template">${template ? renderTemplateForm(template) : renderEmptyEditor("prompts.empty")}</form>
    </div>
  `;
}

function renderTemplateForm(template) {
  const files = templateFiles(template);
  const names = templateFileNames(template);
  const activeFile = selectedTemplateFile(template);
  const isProtectedTemplateFile = TEMPLATE_FILES.includes(activeFile);
  return `
    <div class="form-grid">
      ${field("fields.id", "id", itemId(template), "required")}
      ${field("fields.description", "description", template.description || "")}
      <div class="template-editor field-wide">
        <div class="template-file-tabs" role="tablist" aria-label="${escapeHtml(t("prompts.filesLabel"))}">
          ${names
            .map(
              (file) => `
                <button type="button" class="template-file-tab ${file === activeFile ? "active" : ""}" data-template-file="${escapeHtml(file)}" role="tab" aria-selected="${
                file === activeFile ? "true" : "false"
              }">
                  <span class="template-file-name">${escapeHtml(file.toLowerCase())}</span>
                  <small class="template-file-badge">${escapeHtml(templateFileBadge(file))}</small>
                </button>
              `
            )
            .join("")}
          ${renderTemplateAddFileControl()}
        </div>
        <div class="template-editor-shell">
          <div class="template-file-meta">
            <strong>${escapeHtml(activeFile)}</strong>
            <span>${escapeHtml(templateFileHelp(activeFile))}</span>
            ${!isProtectedTemplateFile ? actionButton(`template-delete-file:${activeFile}`, "actions.removeFile", "danger") : ""}
          </div>
          <textarea name="file:${escapeHtml(activeFile)}" class="template-text template-text-large">${escapeHtml(files[activeFile] || "")}</textarea>
        </div>
      </div>
    </div>
    <div class="button-row form-actions">
      ${actionButton("template-ai-fill-open", "actions.aiFill", "secondary")}
      ${actionButton("template-save", "actions.save", "primary")}
    </div>
  `;
}

function renderAiFillDialog() {
  if (!state.aiFillOpen) return "";
  const template = selectedTemplate();
  if (!template) return "";
  const targetFiles = aiFillTargetFiles(template);
  const referenceFiles = aiFillReferenceFiles(template);
  const llmProfiles = collection("llm");
  const selectedProfile = llmProfiles.some((profile) => itemId(profile) === state.aiFillProfile)
    ? state.aiFillProfile
    : llmProfiles[0]
      ? itemId(llmProfiles[0])
      : "";
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal-panel ai-fill-dialog" role="dialog" aria-modal="true" aria-labelledby="ai-fill-title">
        <header class="modal-header">
          <div>
            <h3 id="ai-fill-title">${escapeHtml(t("prompts.aiFillTitle"))}</h3>
            <p>${escapeHtml(t("prompts.aiFillSubtitle"))}</p>
          </div>
          ${actionButton("template-ai-fill-close", "actions.cancel", "secondary")}
        </header>
        <form class="form-grid" data-form="template-ai-fill">
          ${selectField("fields.llmProfile", "llm_profile", optionList(llmProfiles, selectedProfile), "required")}
          ${textareaField("prompts.aiInstruction", "instruction", state.aiFillInstruction, 'class="ai-fill-instruction"')}
          ${textareaField(
            "prompts.aiDescription",
            "description",
            state.aiFillDescription,
            'class="ai-fill-description" required placeholder="' + escapeHtml(t("prompts.aiDescriptionPlaceholder")) + '"'
          )}
          <section class="field field-wide ai-file-section">
            <span>${escapeHtml(t("prompts.aiGenerateFiles"))}</span>
            <div class="file-chip-grid">
              ${targetFiles.map((file) => `<span class="file-chip locked">${escapeHtml(file)}</span>`).join("")}
            </div>
          </section>
          <section class="field field-wide ai-file-section">
            <label class="check-field inline-check">
              <input type="checkbox" name="use_references" data-ai-reference-toggle ${state.aiFillReferenceEnabled ? "checked" : ""} />
              <span>${escapeHtml(t("prompts.aiUseReferences"))}</span>
            </label>
            ${
              state.aiFillReferenceEnabled
                ? `<div class="file-chip-grid selectable">
                    ${targetFiles
                      .map(
                        (file) => `<label class="file-chip check-chip"><input type="checkbox" name="reference_file" value="${escapeHtml(file)}" ${
                          referenceFiles.includes(file) ? "checked" : ""
                        } /><span>${escapeHtml(file)}</span></label>`
                      )
                      .join("")}
                  </div>`
                : ""
            }
          </section>
        </form>
        <footer class="button-row modal-actions">
          ${actionButton("template-ai-fill-close", "actions.cancel", "secondary")}
          ${actionButton("template-ai-fill-run", "actions.generate", "primary", !llmProfiles.length)}
        </footer>
      </section>
    </div>
  `;
}

function renderExport() {
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("export.title"))}</h2><p>${escapeHtml(t("export.subtitle"))}</p></div>
      <div class="button-row">${actionButton("config-export", "actions.export", "primary")}</div>
    </header>
    <div class="export-grid">
      ${renderCodePanel("export.primary", redact(state.config))}
      ${renderCodePanel("export.resolved", redact(state.exportResult?.config || state.config))}
      ${renderCodePanel("export.generated", buildGeneratedPreview())}
    </div>
  `;
}

function buildGeneratedPreview() {
  const agents = collection("agents");
  return {
    agent_ids: agents.map((agent) => itemId(agent)),
    env_ports: Object.fromEntries(agents.map((agent) => [itemId(agent), agent.host_port || ""])),
    export_path: state.exportResult?.path || ""
  };
}

function renderCodePanel(titleKey, value) {
  return `<section class="code-panel"><h3>${escapeHtml(t(titleKey))}</h3><pre>${escapeHtml(
    JSON.stringify(value, null, 2)
  )}</pre></section>`;
}

function renderEmptyEditor(key) {
  return `<div class="empty-state">${escapeHtml(t(key))}</div>`;
}

function readForm(form) {
  return new FormData(form);
}

function keepSecret(formData, key, existing) {
  const value = String(formData.get(key) || "");
  return value === "••••••••" ? existing || "" : value;
}

function agentFromForm(form) {
  const data = readForm(form);
  const current = selectedAgent() || {};
  const matrix = current.matrix || {};
  return cleanEmptyValues({
    ...current,
    id: requireString(data, "id"),
    enabled: true,
    host_port: requireNumber(data, "host_port", { min: 1, max: 65535 }),
    image: String(data.get("image") || "").trim(),
    llm_profile: requireString(data, "llm_profile"),
    vision_profile: String(data.get("vision_profile") || ""),
    matrix_profile: requireString(data, "matrix_profile"),
    mcp_profile: String(data.get("mcp_profile") || ""),
    prompt_template: String(data.get("prompt_template") || ""),
    skill_bundles: fromLines(String(data.get("skill_bundles") || "")),
    template_apply_mode: String(data.get("template_apply_mode") || "keep"),
    proactive: {
      ...(current.proactive || {}),
      enabled: data.get("proactive_enabled") === "on",
      target: String(data.get("proactive_target") || "").trim(),
      random_min_minutes: parseOptionalNumber(data.get("proactive_random_min_minutes"), fieldDisplayName("proactive_random_min_minutes"), { min: 1 }),
      random_max_minutes: parseOptionalNumber(data.get("proactive_random_max_minutes"), fieldDisplayName("proactive_random_max_minutes"), { min: 1 }),
      poll_seconds: parseOptionalNumber(data.get("proactive_poll_seconds"), fieldDisplayName("proactive_poll_seconds"), { min: 30 }),
      quiet_hours: String(data.get("proactive_quiet_hours") || "").trim(),
      timezone: String(data.get("proactive_timezone") || "").trim(),
      channel: String(data.get("proactive_channel") || "").trim(),
      agent_url: String(data.get("proactive_agent_url") || "").trim(),
      prompt: String(data.get("proactive_prompt") || "").trim()
    },
    matrix: {
      ...matrix,
      external_peers: requireLines(data, "matrix_external_peers")
    },
    environment: readJsonField(data, "environment", {})
  });
}

function profileFromForm(kind, form) {
  const data = readForm(form);
  const current = collection(kind).find((item) => itemId(item) === state[`selected${kind}Id`]) || {};
  const base = { ...current, id: String(data.get("id") || "").trim() };
  if (kind === "llm") {
    const family = requireString(data, "provider_family");
    return cleanEmptyValues({
      ...base,
      id: requireString(data, "id"),
      provider_family: family,
      provider_alias: requireString(data, "provider_alias"),
      base_url: validateUrlLike(data.get("base_url"), "base_url", { required: family === "custom" }),
      model: requireString(data, "model"),
      wire_api: requireString(data, "wire_api"),
      timeout_secs: requireNumber(data, "timeout_secs", { min: 1 }),
      api_key: keepSecret(data, "api_key", current.api_key),
      kind: String(data.get("kind") || "").trim(),
      temperature: parseOptionalFloat(data.get("temperature"), fieldDisplayName("temperature"), { min: 0, max: 2 }),
      max_tokens: parseOptionalNumber(data.get("max_tokens"), fieldDisplayName("max_tokens"), { min: 1 }),
      requires_openai_auth: data.get("requires_openai_auth") === "on",
      fallback: fromLines(String(data.get("fallback") || "")),
      fallback_models: fromLines(String(data.get("fallback_models") || "")),
      extra_headers: readJsonField(data, "extra_headers", {}),
      merge_system_into_user: data.get("merge_system_into_user") === "on",
      provider_extra: readJsonField(data, "provider_extra", undefined),
      pricing: readJsonField(data, "pricing", {}),
      native_tools: parseOptionalBoolean(String(data.get("native_tools") || "")),
      think: parseOptionalBoolean(String(data.get("think") || "")),
      chat_template_kwargs: readJsonField(data, "chat_template_kwargs", undefined),
      tls_ca_cert_path: String(data.get("tls_ca_cert_path") || "").trim(),
      auth_mode: String(data.get("auth_mode") || ""),
      oauth_client_id: keepSecret(data, "oauth_client_id", current.oauth_client_id),
      oauth_client_secret: keepSecret(data, "oauth_client_secret", current.oauth_client_secret),
      oauth_project: String(data.get("oauth_project") || "").trim(),
      num_ctx: parseOptionalNumber(data.get("num_ctx"), fieldDisplayName("num_ctx"), { min: 1 }),
      num_predict: parseOptionalNumber(data.get("num_predict"), fieldDisplayName("num_predict")),
      temperature_override: parseOptionalFloat(data.get("temperature_override"), fieldDisplayName("temperature_override"), { min: 0, max: 2 })
    });
  }
  if (kind === "vision") {
    const family = requireString(data, "provider_family");
    return cleanEmptyValues({
      ...base,
      id: requireString(data, "id"),
      provider_family: family,
      provider_alias: requireString(data, "provider_alias"),
      base_url: validateUrlLike(data.get("base_url"), "base_url", { required: true }),
      model: requireString(data, "model"),
      wire_api: requireString(data, "wire_api"),
      timeout_secs: requireNumber(data, "timeout_secs", { min: 1 }),
      api_key: keepSecret(data, "api_key", current.api_key),
      allow_remote_fetch: data.get("allow_remote_fetch") === "on",
      max_images: requireNumber(data, "max_images", { min: 1, max: 16 }),
      max_image_size_mb: requireNumber(data, "max_image_size_mb", { min: 1, max: 20 }),
      max_image_turns: requireNumber(data, "max_image_turns", { min: 0 })
    });
  }
  if (kind === "matrix") {
    return cleanEmptyValues({
      ...base,
      id: requireString(data, "id"),
      homeserver: validateUrlLike(data.get("homeserver"), "homeserver", { required: true }),
      user_id: String(data.get("user_id") || "").trim(),
      device_id: String(data.get("device_id") || "").trim(),
      access_token: keepSecret(data, "access_token", current.access_token),
      password: keepSecret(data, "password", current.password),
      recovery_key: keepSecret(data, "recovery_key", current.recovery_key),
      allowed_rooms: fromLines(String(data.get("allowed_rooms") || "")),
      mention_only: data.get("mention_only") === "on",
      interrupt_on_new_message: data.get("interrupt_on_new_message") === "on",
      reply_in_thread: data.get("reply_in_thread") === "on",
      ack_reactions: data.get("ack_reactions") === "on",
      stream_mode: String(data.get("stream_mode") || "multi_message"),
      multi_message_delay_ms: parseOptionalNumber(data.get("multi_message_delay_ms"), fieldDisplayName("multi_message_delay_ms"), { min: 0 }),
      channel_debounce_ms: parseOptionalNumber(data.get("channel_debounce_ms"), fieldDisplayName("channel_debounce_ms"), { min: 0 }),
      draft_update_interval_ms: parseOptionalNumber(data.get("draft_update_interval_ms"), fieldDisplayName("draft_update_interval_ms"), { min: 50 }),
      approval_timeout_secs: parseOptionalNumber(data.get("approval_timeout_secs"), fieldDisplayName("approval_timeout_secs"), { min: 1 }),
      excluded_tools: fromLines(String(data.get("excluded_tools") || "")),
      reply_min_interval_secs: parseOptionalNumber(data.get("reply_min_interval_secs"), fieldDisplayName("reply_min_interval_secs"), { min: 0 }),
      reply_queue_depth_max: parseOptionalNumber(data.get("reply_queue_depth_max"), fieldDisplayName("reply_queue_depth_max"), { min: 0 }),
      host_ip: String(data.get("host_ip") || "").trim()
    });
  }
  return {
    ...base,
    id: requireString(data, "id"),
    server_name: String(data.get("server_name") || "").trim(),
    transport: String(data.get("transport") || "").trim(),
    url: validateUrlLike(data.get("url"), "url"),
    token: keepSecret(data, "token", current.token),
    timeout_secs: parseOptionalNumber(data.get("timeout_secs"), fieldDisplayName("timeout_secs"), { min: 1 }) || 0,
    deferred_loading: data.get("deferred_loading") === "on"
  };
}

function templateFromForm(form) {
  const data = readForm(form);
  const current = selectedTemplate() || {};
  const activeFile = selectedTemplateFile(current);
  const files = { ...templateFiles(current) };
  if (activeFile) files[activeFile] = String(data.get(`file:${activeFile}`) || "");
  TEMPLATE_FILES.forEach((file) => {
    if (!(file in files)) files[file] = DEFAULT_TEMPLATE_FILES[file] || "";
  });
  return {
    ...current,
    id: String(data.get("id") || "").trim(),
    description: String(data.get("description") || ""),
    files
  };
}

function skillsSettingsFromForm(form) {
  const data = readForm(form);
  return cleanEmptyValues({
    ...(state.config.skills || {}),
    allow_scripts: data.get("allow_scripts") === "on",
    open_skills_enabled: data.get("open_skills_enabled") === "on",
    registry_url: validateUrlLike(data.get("registry_url"), "registry_url"),
    prompt_injection_mode: String(data.get("prompt_injection_mode") || "full"),
    extra_registries: readJsonField(data, "extra_registries", []),
    skill_creation: {
      ...(state.config.skills?.skill_creation || {}),
      enabled: data.get("skill_creation_enabled") === "on",
      max_skills: parseOptionalNumber(data.get("skill_creation_max_skills"), fieldDisplayName("skill_creation_max_skills"), { min: 1 }) || 500,
      similarity_threshold: parseOptionalFloat(data.get("skill_creation_similarity_threshold"), fieldDisplayName("skill_creation_similarity_threshold"), { min: 0, max: 1 }) ?? 0.85
    },
    install_suggestions: {
      ...(state.config.skills?.install_suggestions || {}),
      enabled: data.get("install_suggestions_enabled") === "on"
    },
    skill_improvement: {
      ...(state.config.skills?.skill_improvement || {}),
      enabled: data.get("skill_improvement_enabled") === "on",
      cooldown_secs: parseOptionalNumber(data.get("skill_improvement_cooldown_secs"), fieldDisplayName("skill_improvement_cooldown_secs"), { min: 0 }) ?? 3600,
      nudge_interval_iterations:
        parseOptionalNumber(data.get("skill_improvement_nudge_interval_iterations"), fieldDisplayName("skill_improvement_nudge_interval_iterations"), { min: 0 }) ?? 10,
      max_review_iterations:
        parseOptionalNumber(data.get("skill_improvement_max_review_iterations"), fieldDisplayName("skill_improvement_max_review_iterations"), { min: 1 }) ?? 8
    }
  });
}

function skillBundleFromForm(form) {
  const data = readForm(form);
  const current = selectedSkillBundle() || {};
  return cleanEmptyValues({
    ...current,
    id: requireString(data, "id"),
    directory: String(data.get("directory") || "").trim(),
    include: fromLines(String(data.get("include") || "")),
    exclude: fromLines(String(data.get("exclude") || ""))
  });
}

function skillCreateFromForm(form) {
  const data = readForm(form);
  const name = requireString(data, "name");
  return {
    name,
    frontmatter: cleanEmptyValues({
      name,
      description: requireString(data, "description"),
      version: String(data.get("version") || "0.1.0").trim(),
      tags: fromLines(String(data.get("tags") || ""))
    }),
    body: ""
  };
}

function skillDocumentFromForm(form) {
  const data = readForm(form);
  return {
    frontmatter: cleanEmptyValues({
      name: requireString(data, "name"),
      description: requireString(data, "description"),
      version: String(data.get("version") || "").trim(),
      author: String(data.get("author") || "").trim(),
      license: String(data.get("license") || "").trim(),
      category: String(data.get("category") || "").trim(),
      tags: fromLines(String(data.get("tags") || ""))
    }),
    body: String(data.get("body") || "")
  };
}

async function saveItem(kind, selectedId, item) {
  const payload = cleanPayload(item);
  const isDraft = item._draft === true;
  const encoded = encodeURIComponent(selectedId || itemId(item));
  if (selectedId && !isDraft) {
    return api(kind === "agents" ? `/api/agents/${encoded}` : `/api/profiles/${kind}/${encoded}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    });
  }
  return api(kind === "agents" ? "/api/agents" : `/api/profiles/${kind}`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

async function saveTemplate(selectedId, template) {
  const payload = cleanPayload(template);
  if (selectedId && template._draft !== true) {
    return api(`/api/prompt-templates/${encodeURIComponent(selectedId)}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    });
  }
  return api("/api/prompt-templates", { method: "POST", body: JSON.stringify(payload) });
}

function nextId(prefix, items) {
  let index = items.length + 1;
  const ids = new Set(items.map(itemId));
  while (ids.has(`${prefix}-${index}`)) index += 1;
  return `${prefix}-${index}`;
}

async function confirmDanger(messageKey) {
  return confirmDialog(t(messageKey));
}

async function runImageAction(action, successKey, extra = {}) {
  return runAction(async () => {
    const result = await api("/api/docker/images/action", {
      method: "POST",
      body: JSON.stringify({ action, ...extra })
    });
    await refreshDockerImages();
    return result;
  }, successKey);
}

async function buildManagedImage(kind) {
  if (!state.dockerImages) await refreshDockerImages();
  const acknowledged = state.dockerImages?.state?.acknowledged?.[kind]?.accepted === true;
  if (!acknowledged && !(await confirmDanger(kind === "python" ? "confirm.buildPythonImage" : "confirm.buildRootImage"))) return;
  const recommended = state.dockerImages?.recommended || {};
  const target = kind === "python" ? recommended.python : recommended.root;
  return runImageAction(`build-${kind}`, "messages.imageActionDone", {
    base_image: recommended.official || DEFAULT_ZEROCLAW_IMAGE,
    target_image: target,
    acknowledge_risk: true
  });
}

async function handleAction(action) {
  if (action.startsWith("agent-start:")) return controlAgent(action.split(":")[1], "start");
  if (action.startsWith("agent-stop:")) return controlAgent(action.split(":")[1], "stop");
  if (action.startsWith("agent-restart:")) return controlAgent(action.split(":")[1], "restart");
  if (action.startsWith("agent-logs:")) return runAction(() => refreshAgentLogs(action.split(":")[1]));
  if (action.startsWith("agent-download-logs:")) {
    const id = action.split(":")[1];
    window.location.href = `/api/agents/${encodeURIComponent(id)}/logs/download?tail=${encodeURIComponent(state.logTail)}`;
    return;
  }
  if (action.startsWith("agent-edit:")) {
    state.selectedTab = "agents";
    state.selectedAgentId = action.split(":")[1];
    render();
    return;
  }
  if (action.startsWith("agent-delete:")) return deleteAgent(action.split(":")[1]);
  if (action === "agent-advanced-actions-toggle") {
    state.agentAdvancedActionsOpen = !state.agentAdvancedActionsOpen;
    render();
    return;
  }

  if (action === "refresh-all-status") {
    return runAction(async () => {
      await refreshDashboard();
      await Promise.all(collection("agents").map((agent) => refreshAgentLogs(itemId(agent))));
    });
  }
  if (action === "refresh-docker-resources") {
    return runAction(refreshDockerResources);
  }
  if (action === "refresh-docker-images") {
    return runAction(refreshDockerImages);
  }
  if (action === "image-pull-official") {
    return runImageAction("pull-official", "messages.imageActionDone");
  }
  if (action === "image-build-python") {
    return buildManagedImage("python");
  }
  if (action === "image-build-root") {
    return buildManagedImage("root");
  }
  if (action === "resource-delete-cancel") {
    state.pendingResourceDelete = null;
    state.pendingResourceDeleteInput = "";
    render();
    return;
  }
  if (action === "resource-delete-confirm") {
    return confirmResourceDelete();
  }
  if (action.startsWith("resource-")) {
    return handleResourceAction(action);
  }
  if (action === "agent-new") {
    state.selectedAgentId = "";
    state.config.agents.unshift(defaultAgent(nextId("agent", collection("agents"))));
    state.selectedAgentId = itemId(state.config.agents[0]);
    render();
  }
  if (action === "agent-duplicate") {
    const source = selectedAgent();
    if (!source) return;
    const copy = cloneData(source);
    copy.id = nextId(`${itemId(source)}-copy`, collection("agents"));
    delete copy.name;
    if (!copy.image) copy.image = DEFAULT_ZEROCLAW_IMAGE;
    copy.proactive = { ...cloneData(DEFAULT_PROACTIVE), ...(copy.proactive || {}) };
    copy._draft = true;
    state.config.agents.unshift(copy);
    state.selectedAgentId = copy.id;
    render();
  }
  if (action === "agent-save") {
    let item;
    try {
      item = agentFromForm(document.querySelector('[data-form="agent"]'));
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    return runAction(async () => {
      await saveItem("agents", state.selectedAgentId, item);
      state.selectedAgentId = itemId(item);
    }, "messages.saved");
  }
  if (action === "agent-validate") {
    const id = itemId(selectedAgent());
    try {
      setBusy(true);
      clearToast();
      state.validationResult = await api(`/api/agents/${encodeURIComponent(id)}/validate`, { method: "POST", body: "{}" });
      if (state.validationResult.valid) {
        showNotice(t("messages.validationPassed"));
      } else {
        showError(t("messages.validationFailed"));
      }
    } catch (error) {
      showError(error.message || String(error));
    } finally {
      state.busy = false;
      render();
    }
    return;
  }
  if (action === "agent-apply-template") {
    const agent = selectedAgent();
    if (!agent) return;
    const form = document.querySelector('[data-form="agent"]');
    let item;
    try {
      item = agentFromForm(form);
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    const data = new FormData(form);
    const mode = String(data.get("template_apply_mode") || "keep");
    if (mode === "overwrite" && !(await confirmDanger("confirm.overwriteWorkspace"))) return;
    return runAction(
      async () => {
        await saveItem("agents", state.selectedAgentId, item);
        state.selectedAgentId = itemId(item);
        const result = await api(`/api/agents/${encodeURIComponent(itemId(item))}/apply-template`, {
          method: "POST",
          body: JSON.stringify({ mode })
        });
        state.dashboardRequested = false;
        return result;
      },
      "messages.templateApplied"
    );
  }
  if (action === "agent-sync-to-runtime" || action === "agent-sync-from-runtime") {
    const agent = selectedAgent();
    if (!agent) return;
    const id = itemId(agent);
    const endpoint = action === "agent-sync-to-runtime" ? "sync-to-runtime" : "sync-from-runtime";
    const successKey = action === "agent-sync-to-runtime" ? "messages.syncedToRuntime" : "messages.syncedFromRuntime";
    return runAction(async () => {
      await api(`/api/agents/${encodeURIComponent(id)}/${endpoint}`, { method: "POST", body: "{}" });
    }, successKey);
  }
  if (action === "agent-reset-matrix-state") return resetMatrixState();
  if (action === "agent-delete-current") return deleteAgent(state.selectedAgentId);

  for (const kind of ["llm", "vision", "matrix", "mcp"]) {
    if (action === `${kind}-new`) {
      const item = createProfileDraft(kind);
      state.config.profiles[kind].unshift(item);
      state[`selected${kind}Id`] = item.id;
      render();
    }
    if (action === `${kind}-delete-current`) return deleteProfile(kind, state[`selected${kind}Id`]);
  }
  if (action === "profile-save") {
    const kind = document.querySelector(".form-panel")?.dataset.form;
    let item;
    try {
      item = profileFromForm(kind, document.querySelector(`[data-form="${kind}"]`));
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    return runAction(async () => {
      await saveItem(kind, state[`selected${kind}Id`], item);
      state[`selected${kind}Id`] = itemId(item);
    }, "messages.saved");
  }

  if (action === "template-new") {
    const template = { id: nextId("template", collection("prompt_templates")), files: defaultTemplateFiles(), _draft: true };
    state.config.prompt_templates.unshift(template);
    state.selectedTemplateId = template.id;
    state.selectedTemplateFile = TEMPLATE_FILES[0];
    render();
  }
  if (action === "template-duplicate") {
    const source = selectedTemplate();
    if (!source) return;
    const copy = cloneData(source);
    copy.id = nextId(`${itemId(source)}-copy`, collection("prompt_templates"));
    copy._draft = true;
    state.config.prompt_templates.unshift(copy);
    state.selectedTemplateId = copy.id;
    state.selectedTemplateFile = selectedTemplateFile(copy);
    render();
  }
  if (action === "template-add-file") {
    const template = selectedTemplate();
    if (!template) return;
    updateTemplateDraftFromForm();
    state.pendingTemplateFileName = "RHYTHM.md";
    render();
    queueMicrotask(() => document.querySelector("[data-template-new-file]")?.select());
  }
  if (action === "template-cancel-file") {
    state.pendingTemplateFileName = "";
    render();
  }
  if (action === "template-confirm-file") {
    const template = selectedTemplate();
    if (!template) return;
    const input = document.querySelector("[data-template-new-file]")?.value || state.pendingTemplateFileName;
    let filename;
    try {
      filename = normalizeTemplateFilename(input);
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    updateTemplateDraftFromForm();
    template.files = { ...templateFiles(template), [filename]: templateFiles(template)[filename] || "" };
    state.selectedTemplateFile = filename;
    state.pendingTemplateFileName = "";
    render();
  }
  if (action.startsWith("template-delete-file:")) {
    const template = selectedTemplate();
    const filename = action.slice("template-delete-file:".length);
    if (!template || TEMPLATE_FILES.includes(filename) || !(await confirmDanger("confirm.deleteTemplateFile"))) return;
    updateTemplateDraftFromForm();
    const files = { ...templateFiles(template) };
    delete files[filename];
    template.files = files;
    state.selectedTemplateFile = TEMPLATE_FILES[0];
    render();
  }
  if (action === "template-save") {
    const template = templateFromForm(document.querySelector('[data-form="template"]'));
    return runAction(async () => {
      await saveTemplate(state.selectedTemplateId, template);
      state.selectedTemplateId = itemId(template);
    }, "messages.saved");
  }
  if (action === "template-ai-fill-open") return openAiFillDialog();
  if (action === "template-ai-fill-close") {
    state.aiFillOpen = false;
    render();
    return;
  }
  if (action === "template-ai-fill-run") {
    try {
      return await runAiFill();
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
  }
  if (action === "template-delete-current") return deleteTemplate(state.selectedTemplateId);
  if (action === "skills-settings-save") {
    let skillsConfig;
    try {
      skillsConfig = skillsSettingsFromForm(document.querySelector('[data-form="skills-settings"]'));
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    return runAction(async () => {
      await api("/api/config", { method: "PUT", body: JSON.stringify({ ...state.config, skills: skillsConfig }) });
    }, "messages.saved");
  }
  if (action === "skill-bundle-new") {
    const bundle = { id: nextId("bundle", skillBundles()), directory: "", include: [], exclude: [], _draft: true };
    state.config.skill_bundles.unshift(bundle);
    state.selectedSkillBundleId = bundle.id;
    state.selectedSkillName = "";
    render();
    return;
  }
  if (action.startsWith("skill-bundle-copy-path:")) {
    return copySkillPath(action.slice("skill-bundle-copy-path:".length));
  }
  if (action.startsWith("skill-bundle-open-folder:")) {
    return openSkillFolder(action.slice("skill-bundle-open-folder:".length));
  }
  if (action.startsWith("skill-copy-path:")) {
    const [, bundleId = "", skillName = ""] = action.match(/^skill-copy-path:([^:]*):(.*)$/) || [];
    return copySkillPath(bundleId, skillName);
  }
  if (action.startsWith("skill-open-folder:")) {
    const [, bundleId = "", skillName = ""] = action.match(/^skill-open-folder:([^:]*):(.*)$/) || [];
    return openSkillFolder(bundleId, skillName);
  }
  if (action === "skill-bundle-save") {
    let bundle;
    try {
      bundle = skillBundleFromForm(document.querySelector('[data-form="skill-bundle"]'));
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    return runAction(async () => {
      const selected = state.selectedSkillBundleId;
      const isDraft = selected && selectedSkillBundle()?._draft === true;
      if (selected && !isDraft) {
        await api(`/api/skills/bundles/${encodeURIComponent(selected)}`, { method: "PUT", body: JSON.stringify(bundle) });
      } else {
        await api("/api/skills/bundles", { method: "POST", body: JSON.stringify(bundle) });
      }
      state.selectedSkillBundleId = itemId(bundle);
    }, "messages.saved");
  }
  if (action === "skill-bundle-delete-current") return deleteSkillBundle(state.selectedSkillBundleId);
  if (action === "skill-refresh") {
    return runAction(async () => {
      await refreshSkillList();
      state.selectedSkillName = selectedSkill()?.name || "";
      if (state.selectedSkillName) await refreshSkillDocument();
    });
  }
  if (action === "skill-new-toggle") {
    state.skillNewOpen = !state.skillNewOpen;
    render();
    return;
  }
  if (action === "skill-create") {
    let payload;
    try {
      payload = skillCreateFromForm(document.querySelector('[data-form="skill-create"]'));
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    return runAction(async () => {
      await api(`/api/skills/bundles/${encodeURIComponent(state.selectedSkillBundleId)}/skills`, { method: "POST", body: JSON.stringify(payload) });
      state.skillNewOpen = false;
      state.selectedSkillName = payload.name;
      await refreshSkillList();
      await refreshSkillDocument();
    }, "messages.saved");
  }
  if (action === "skill-save") {
    let payload;
    try {
      payload = skillDocumentFromForm(document.querySelector('[data-form="skill-doc"]'));
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
    return runAction(async () => {
      const bundle = state.selectedSkillBundleId;
      const skill = state.selectedSkillName;
      const result = await api(`/api/skills/bundles/${encodeURIComponent(bundle)}/skills/${encodeURIComponent(skill)}`, { method: "PUT", body: JSON.stringify(payload) });
      state.skillDocuments[`${bundle}:${skill}`] = result;
      await refreshSkillList(bundle);
    }, "messages.saved");
  }
  if (action === "skill-archive") return archiveSkill();
  if (action === "skill-file-load") return loadSkillSupportFile();
  if (action === "skill-file-save") return saveSkillSupportFile();
  if (action === "skill-file-download") return downloadSkillSupportFile();
  if (action === "skill-file-delete") return deleteSkillSupportFile();
  if (action === "support-file-create-open") {
    openSupportFileDialog("create");
    return;
  }
  if (action === "support-file-upload-open") {
    openSupportFileDialog("upload");
    return;
  }
  if (action === "support-file-dialog-close") {
    closeSupportFileDialog();
    return;
  }
  if (action === "support-file-create-save") return createSupportTextFileFromDialog();
  if (action === "support-file-upload-save") return uploadSupportTextFileFromDialog();
  if (action === "skills-enable-scripts") return enableSkillScripts();
  if (action === "config-export") {
    return runAction(async () => {
      state.exportResult = await api("/api/export", { method: "POST", body: JSON.stringify({ filename: "resolved.yaml" }) });
    }, "messages.exported");
  }
}

function parseResourceAction(action) {
  const [prefix, encoded = ""] = action.split(":", 2);
  const resourceAction = prefix.replace("resource-", "");
  const decoded = decodeURIComponent(encoded);
  const separator = decoded.indexOf(":");
  if (separator < 0) return { action: resourceAction, kind: "", name: "" };
  return {
    action: resourceAction,
    kind: decoded.slice(0, separator),
    name: decoded.slice(separator + 1)
  };
}

async function handleResourceAction(actionText) {
  const resource = parseResourceAction(actionText);
  if (!resource.kind || !resource.name) return;
  const payload = { action: resource.action, kind: resource.kind, name: resource.name };
  if (resource.action === "delete") {
    state.pendingResourceDelete = {
      kind: resource.kind,
      name: resource.name,
      classification: findResourceClassification(resource.kind, resource.name)
    };
    state.pendingResourceDeleteInput = "";
    render();
    return;
  }
  if (resource.action === "migrate") {
    const targetName = await promptDialog(t("resources.migrateTargetPrompt"), `${resource.name}-migrated`);
    if (!targetName || !targetName.trim()) return;
    payload.target_name = targetName.trim();
  }
  await runAction(async () => {
    await api("/api/docker/resources/action", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    await refreshDockerResources();
  }, "messages.resourceActionDone");
}

function findResourceClassification(kind, name) {
  const groupKey = { container: "containers", volume: "volumes", network: "networks" }[kind];
  const group = groupKey ? state.dockerResources?.[groupKey] : null;
  if (!group) return "";
  for (const bucket of ["conflicts", "orphans", "legacy", "ignored", "adopted", "expected"]) {
    const row = (group[bucket] || []).find((item) => item.name === name);
    if (row) return row.classification || "";
  }
  return "";
}

async function confirmResourceDelete() {
  const pending = state.pendingResourceDelete;
  if (!pending || state.pendingResourceDeleteInput !== pending.name) return;
  await runAction(async () => {
    await api("/api/docker/resources/action", {
      method: "POST",
      body: JSON.stringify({ action: "delete", kind: pending.kind, name: pending.name })
    });
    state.pendingResourceDelete = null;
    state.pendingResourceDeleteInput = "";
    await refreshDockerResources();
  }, "messages.resourceActionDone");
}

async function controlAgent(agentId, operation) {
  const messageKeys = {
    start: "messages.started",
    stop: "messages.stopped",
    restart: "messages.restarted"
  };
  return runAction(async () => {
    const result = await api(`/api/agents/${encodeURIComponent(agentId)}/${operation}`, { method: "POST", body: "{}" });
    state.agentStatuses[agentId] = result;
  }, messageKeys[operation]);
}

async function deleteAgent(agentId) {
  if (!agentId || !(await confirmDanger("confirm.deleteAgent"))) return;
  if (selectedAgent()?._draft === true) {
    removeAgentLocalState(agentId);
    state.selectedAgentId = "";
    render();
    return;
  }
  return runAction(async () => {
    await api(`/api/agents/${encodeURIComponent(agentId)}`, { method: "DELETE" });
    removeAgentLocalState(agentId);
    state.selectedAgentId = "";
    if (state.selectedTab === "dashboard") await refreshDashboard();
  }, "messages.deleted");
}

async function resetMatrixState() {
  const agent = selectedAgent();
  const agentId = itemId(agent);
  if (!agentId) return;
  try {
    setBusy(true);
    clearToast();
    const status = await api(`/api/agents/${encodeURIComponent(agentId)}/status`);
    state.agentStatuses[agentId] = status;
    if (status.running) {
      showError(t("messages.resetMatrixRunning"));
      return;
    }
    if (!(await confirmDialog(t("confirm.resetMatrixState")))) return;
    await api(`/api/agents/${encodeURIComponent(agentId)}/reset-matrix-state`, { method: "POST", body: "{}" });
    await refreshConfig(false);
    showNotice(t("messages.resetMatrixState"));
  } catch (error) {
    showError(error.message || String(error));
  } finally {
    state.busy = false;
    render();
  }
}

async function deleteProfile(kind, id) {
  if (!id || !(await confirmDanger("confirm.deleteProfile"))) return;
  const item = collection(kind).find((profile) => itemId(profile) === id);
  if (item?._draft === true) {
    state.config.profiles[kind] = state.config.profiles[kind].filter((profile) => itemId(profile) !== id);
    state[`selected${kind}Id`] = "";
    render();
    return;
  }
  return runAction(async () => {
    await api(`/api/profiles/${kind}/${encodeURIComponent(id)}`, { method: "DELETE" });
    state[`selected${kind}Id`] = "";
  }, "messages.deleted");
}

async function deleteTemplate(id) {
  if (!id || !(await confirmDanger("confirm.deleteTemplate"))) return;
  const template = collection("prompt_templates").find((item) => itemId(item) === id);
  if (template?._draft === true) {
    state.config.prompt_templates = state.config.prompt_templates.filter((item) => itemId(item) !== id);
    state.selectedTemplateId = "";
    render();
    return;
  }
  return runAction(async () => {
    await api(`/api/prompt-templates/${encodeURIComponent(id)}`, { method: "DELETE" });
    state.selectedTemplateId = "";
  }, "messages.deleted");
}

async function deleteSkillBundle(id) {
  if (!id || !(await confirmDanger("confirm.deleteSkillBundle"))) return;
  const bundle = skillBundles().find((item) => itemId(item) === id);
  if (bundle?._draft === true) {
    state.config.skill_bundles = state.config.skill_bundles.filter((item) => itemId(item) !== id);
    state.selectedSkillBundleId = "";
    render();
    return;
  }
  return runAction(async () => {
    await api(`/api/skills/bundles/${encodeURIComponent(id)}`, { method: "DELETE" });
    delete state.skillBundleSkills[id];
    state.selectedSkillBundleId = "";
    state.selectedSkillName = "";
  }, "messages.deleted");
}

async function archiveSkill() {
  const bundle = state.selectedSkillBundleId;
  const name = state.selectedSkillName;
  if (!bundle || !name || !(await confirmDanger("confirm.archiveSkill"))) return;
  return runAction(async () => {
    await api(`/api/skills/bundles/${encodeURIComponent(bundle)}/skills/${encodeURIComponent(name)}`, { method: "DELETE" });
    delete state.skillDocuments[`${bundle}:${name}`];
    state.selectedSkillName = "";
    await refreshSkillList(bundle);
  }, "messages.deleted");
}

async function loadSkillSupportFile(filePath = "") {
  const form = document.querySelector('[data-form="skill-doc"]');
  let selected = String(filePath || "").trim();
  if (!selected) {
    try {
      selected = supportFilePathFromForm(new FormData(form));
    } catch (error) {
      if (error instanceof FormValidationError) return alertValidation(error);
      throw error;
    }
  }
  if (!selected) return;
  return runAction(async () => {
    state.selectedSkillFile = selected;
    state.skillFilePathDraft = selected;
    try {
      state.skillFileDraft = await fetchSupportFileContent(selected);
    } catch (error) {
      state.skillFileDraft = "";
      showNotice(t("messages.binaryFileSelected"), "info");
    }
  });
}

async function saveSkillSupportFile() {
  const form = document.querySelector('[data-form="skill-doc"]');
  const data = new FormData(form);
  let filePath;
  try {
    filePath = supportFilePathFromForm(data);
  } catch (error) {
    if (error instanceof FormValidationError) return alertValidation(error);
    throw error;
  }
  const content = String(data.get("support_file_content") || "");
  return writeSupportFile(filePath, content);
}

async function createSupportTextFileFromDialog() {
  const form = document.querySelector('[data-form="support-file-dialog"]');
  if (!form) return;
  const data = new FormData(form);
  let filePath;
  try {
    filePath = supportFilePathFromForm(data);
  } catch (error) {
    if (error instanceof FormValidationError) return alertValidation(error);
    throw error;
  }
  const content = String(data.get("support_file_content") || "");
  return writeSupportFile(filePath, content, { closeDialog: true });
}

async function uploadSupportTextFileFromDialog() {
  const form = document.querySelector('[data-form="support-file-dialog"]');
  if (!form) return;
  const data = new FormData(form);
  const file = data.get("support_upload_file");
  if (!file || typeof file.name !== "string" || !file.name) {
    return alertValidation(new FormValidationError(t("messages.requiredField").replace("{field}", fieldDisplayName("support_upload_file")), "support_upload_file"));
  }
  let filePath;
  try {
    filePath = supportFileUploadPathFromForm(data, file);
  } catch (error) {
    if (error instanceof FormValidationError) return alertValidation(error);
    throw error;
  }
  const contentBase64 = await fileToBase64(file);
  return uploadSupportFile(filePath, contentBase64, { closeDialog: true });
}

async function writeSupportFile(filePath, content, { closeDialog = false } = {}) {
  return runAction(async () => {
    await api(`/api/skills/bundles/${encodeURIComponent(state.selectedSkillBundleId)}/skills/${encodeURIComponent(state.selectedSkillName)}/files`, {
      method: "POST",
      body: JSON.stringify({ file_path: filePath, content })
    });
    const parts = supportPathParts(filePath);
    state.selectedSupportType = parts.type;
    state.selectedSkillFile = filePath;
    state.skillFilePathDraft = filePath;
    state.skillFileDraft = content;
    if (closeDialog) state.supportFileDialog = null;
    await refreshSkillDocument();
  }, "messages.saved");
}

async function uploadSupportFile(filePath, contentBase64, { closeDialog = false } = {}) {
  return runAction(async () => {
    const result = await api(`/api/skills/bundles/${encodeURIComponent(state.selectedSkillBundleId)}/skills/${encodeURIComponent(state.selectedSkillName)}/files/upload`, {
      method: "POST",
      body: JSON.stringify({ file_path: filePath, content_base64: contentBase64 })
    });
    const parts = supportPathParts(filePath);
    state.selectedSupportType = parts.type;
    state.selectedSkillFile = filePath;
    state.skillFilePathDraft = filePath;
    state.skillFileDraft = result.text ? await fetchSupportFileContent(filePath) : "";
    if (closeDialog) state.supportFileDialog = null;
    await refreshSkillDocument();
  }, "messages.saved");
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || "").split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error || new Error("file_read_failed"));
    reader.readAsDataURL(file);
  });
}

async function fetchSupportFileContent(filePath) {
  const result = await api(
    `/api/skills/bundles/${encodeURIComponent(state.selectedSkillBundleId)}/skills/${encodeURIComponent(state.selectedSkillName)}/files/${encodeURIComponent(filePath)}`
  );
  return result.content || "";
}

async function enableSkillScripts() {
  return runAction(async () => {
    await api("/api/config", {
      method: "PUT",
      body: JSON.stringify({ ...state.config, skills: { ...(state.config.skills || {}), allow_scripts: true } })
    });
  }, "messages.saved");
}

async function copySkillPath(bundleId, skillName = "") {
  if (!bundleId) return;
  const suffix = skillName ? `/skills/${encodeURIComponent(skillName)}/path` : "/path";
  try {
    const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}${suffix}`);
    const path = result.host_path || result.container_path || "";
    if (!path) {
      await alertDialog(t("messages.pathUnavailable"));
      return;
    }
    try {
      await navigator.clipboard.writeText(path);
      showNotice(t("messages.pathCopied"));
    } catch (_error) {
      await promptDialog(t("messages.copyPathPrompt"), path);
    }
  } catch (error) {
    showError(error.message || String(error));
  } finally {
    render();
  }
}

async function openSkillFolder(bundleId, skillName = "") {
  if (!bundleId) return;
  const suffix = skillName ? `/skills/${encodeURIComponent(skillName)}/open` : "/open";
  try {
    const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}${suffix}`, { method: "POST", body: "{}" });
    if (result.opened) {
      showNotice(t("messages.folderOpenRequested"));
      return;
    }
    const path = result.host_path || result.container_path || "";
    if (path) {
      await promptDialog(t("messages.openFolderFallback"), path);
      return;
    }
    await alertDialog(t("messages.pathUnavailable"));
  } catch (error) {
    showError(error.message || String(error));
  } finally {
    render();
  }
}

async function deleteSkillSupportFile() {
  const form = document.querySelector('[data-form="skill-doc"]');
  let filePath;
  try {
    filePath = supportFilePathFromForm(new FormData(form));
  } catch (error) {
    if (error instanceof FormValidationError) return alertValidation(error);
    throw error;
  }
  if (!filePath || !(await confirmDanger("confirm.deleteSkillFile"))) return;
  return runAction(async () => {
    await api(
      `/api/skills/bundles/${encodeURIComponent(state.selectedSkillBundleId)}/skills/${encodeURIComponent(state.selectedSkillName)}/files/${encodeURIComponent(filePath)}`,
      { method: "DELETE" }
    );
    state.selectedSkillFile = "";
    state.skillFileDraft = "";
    state.skillFilePathDraft = "references/notes.md";
    await refreshSkillDocument();
  }, "messages.deleted");
}

function downloadSkillSupportFile() {
  const form = document.querySelector('[data-form="skill-doc"]');
  if (!form) return;
  let filePath;
  try {
    filePath = supportFilePathFromForm(new FormData(form));
  } catch (error) {
    if (error instanceof FormValidationError) return alertValidation(error);
    throw error;
  }
  window.location.href = `/api/skills/bundles/${encodeURIComponent(state.selectedSkillBundleId)}/skills/${encodeURIComponent(state.selectedSkillName)}/files/${encodeURIComponent(filePath)}/download`;
}

function bindEvents() {
  document.addEventListener("click", async (event) => {
    if (state.dialog) {
      if (event.target.closest("[data-dialog-confirm]")) {
        settleDialog(state.dialog.type === "prompt" ? state.dialog.input : true);
        return;
      }
      if (event.target.closest("[data-dialog-cancel]") || event.target === event.target.closest("[data-dialog-backdrop]")) {
        settleDialog(state.dialog.type === "prompt" ? null : false);
        return;
      }
      return;
    }

    if (event.target.closest("[data-notice-dismiss]")) {
      clearToast();
      render();
      return;
    }

    const tab = event.target.closest("[data-tab]")?.dataset.tab;
    if (tab) {
      state.selectedTab = tab;
      try {
        localStorage.setItem("zeroclaw.webui.selectedTab", tab);
      } catch (_error) {
        // Tab persistence should never block the control surface.
      }
      clearToast();
      render();
      if (tab === "dashboard" && !state.dashboardRequested) {
        await refreshDashboardInBackground();
      }
      if (tab === "images" && !state.dockerImagesRequested) {
        await refreshDockerImagesInBackground();
      }
      if (tab === "resources" && !state.dockerResourcesRequested) {
        await refreshDockerResourcesInBackground();
      }
      return;
    }

    const skillsView = event.target.closest("[data-skills-view]")?.dataset.skillsView;
    if (skillsView) {
      state.selectedSkillsView = SKILLS_VIEWS.includes(skillsView) ? skillsView : "bundles";
      render();
      return;
    }

    const supportType = event.target.closest("[data-support-type]")?.dataset.supportType;
    if (supportType) {
      state.selectedSupportType = SKILL_SUPPORT_DIRS.includes(supportType) ? supportType : "references";
      state.selectedSkillFile = "";
      state.skillFileDraft = "";
      state.skillFilePathDraft = defaultSupportPath(state.selectedSupportType);
      render();
      return;
    }

    for (const kind of ["agents", "llm", "vision", "matrix", "mcp", "templates"]) {
      const selector = event.target.closest(`[data-select-${kind}]`);
      if (selector) {
        const value = selector.dataset[`select${kind[0].toUpperCase()}${kind.slice(1)}`];
        if (kind === "agents") state.selectedAgentId = value;
        else if (kind === "templates") {
          state.selectedTemplateId = value;
          state.selectedTemplateFile = "";
          state.pendingTemplateFileName = "";
        }
        else if (kind === "skillBundles") {
          state.selectedSkillBundleId = value;
          state.selectedSkillName = "";
          state.skillNewOpen = false;
          await refreshSkillList(value);
        }
        else state[`selected${kind}Id`] = value;
        state.validationResult = null;
        render();
        return;
      }
    }

    const skillBundleButton = event.target.closest("[data-select-skill-bundles]");
    if (skillBundleButton) {
      const value = skillBundleButton.dataset.selectSkillBundles;
      state.selectedSkillBundleId = value;
      state.selectedSkillName = "";
      state.skillNewOpen = false;
      await refreshSkillList(value);
      render();
      return;
    }

    const skillName = event.target.closest("[data-skill-name]")?.dataset.skillName;
    if (skillName) {
      state.selectedSkillName = skillName;
      state.selectedSkillFile = "";
      state.skillFileDraft = "";
      state.skillFilePathDraft = defaultSupportPath();
      await refreshSkillDocument(state.selectedSkillBundleId, skillName);
      render();
      return;
    }

    const supportSkill = event.target.closest("[data-support-skill-name]");
    if (supportSkill) {
      const bundleId = supportSkill.dataset.supportSkillBundle;
      const skillName = supportSkill.dataset.supportSkillName;
      if (!bundleId || !skillName) return;
      state.selectedSkillBundleId = bundleId;
      state.selectedSkillName = skillName;
      state.selectedSkillFile = "";
      state.skillFileDraft = "";
      state.skillFilePathDraft = defaultSupportPath();
      if (!state.skillBundleSkills[bundleId]) await refreshSkillList(bundleId);
      await refreshSkillDocument(bundleId, skillName);
      render();
      return;
    }

    const skillFile = event.target.closest("[data-skill-file]")?.dataset.skillFile;
    if (skillFile) {
      state.selectedSkillFile = skillFile;
      state.skillFilePathDraft = skillFile;
      await loadSkillSupportFile(skillFile);
      return;
    }

    const templateFile = event.target.closest("[data-template-file]")?.dataset.templateFile;
    if (templateFile) {
      updateTemplateDraftFromForm();
      state.selectedTemplateFile = templateFile;
      state.pendingTemplateFileName = "";
      render();
      return;
    }

    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action) await handleAction(action);
  });

  document.addEventListener("submit", (event) => event.preventDefault());

  document.addEventListener("input", (event) => {
    if (event.target.matches("[data-dialog-input]")) {
      if (state.dialog) state.dialog.input = event.target.value;
    }
    if (event.target.matches("[data-template-new-file]")) {
      state.pendingTemplateFileName = event.target.value;
    }
    if (event.target.matches("[data-resource-delete-input]")) {
      state.pendingResourceDeleteInput = event.target.value;
      render();
    }
    if (event.target.matches("[data-image-preset]")) {
      const input = document.querySelector("[data-image-input]");
      if (input && event.target.value !== "__custom__") input.value = event.target.value;
    }
  });

  document.addEventListener("keydown", async (event) => {
    if (state.dialog) {
      if (event.key === "Escape") {
        event.preventDefault();
        settleDialog(state.dialog.type === "prompt" ? null : false);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        settleDialog(state.dialog.type === "prompt" ? state.dialog.input : true);
        return;
      }
      return;
    }
    if (!event.target.matches("[data-template-new-file]")) return;
    if (event.key === "Enter") {
      event.preventDefault();
      await handleAction("template-confirm-file");
    }
    if (event.key === "Escape") {
      event.preventDefault();
      await handleAction("template-cancel-file");
    }
  });

  document.addEventListener("change", (event) => {
    if (event.target.matches("[data-agent-profile-kind]") && event.target.value === ADD_NEW_PROFILE_VALUE) {
      createProfileFromAgentSelect(event.target);
      return;
    }
    if (event.target.matches("[data-log-tail]")) {
      state.logTail = Math.max(1, Math.min(2000, parseNumber(event.target.value, 200)));
      render();
    }
    if (event.target.matches("[data-auto-refresh]")) {
      state.autoRefresh = event.target.checked;
      configureAutoRefresh();
      render();
    }
    if (event.target.matches("[data-llm-provider]")) {
      applyLlmPresetToForm(event.target.form, event.target.value);
    }
    if (event.target.matches("[data-ai-reference-toggle]")) {
      syncAiFillDraftFromForm();
      renderAiFillPreservingScroll();
    }
    if (event.target.matches('[name="reference_file"]')) {
      syncAiFillDraftFromForm();
    }
    if (event.target.matches('[name="support_file_type"], [name="support_file_name"]')) {
      try {
        state.skillFilePathDraft = supportFilePathFromForm(new FormData(event.target.form));
      } catch (_error) {
        // Keep partially typed paths in the form; validation runs on load/save/delete.
      }
      render();
    }
    if (event.target.matches('[name="support_upload_file"]')) {
      const file = event.target.files?.[0];
      const form = event.target.form;
      const nameInput = form?.elements?.support_file_name;
      if (file?.name && nameInput && !String(nameInput.value || "").trim()) {
        nameInput.value = file.name;
      }
    }
  });
}

function applyLlmPresetToForm(form, family) {
  if (!form) return;
  const preset = LLM_PRESETS[family] || LLM_PRESETS.openai;
  for (const key of LLM_PROVIDER_FIELDS) {
    const input = form.elements[key];
    if (!input || key === "provider_family") continue;
    input.value = preset[key] ?? "";
  }
}

function configureAutoRefresh() {
  if (state.autoRefreshTimer) window.clearInterval(state.autoRefreshTimer);
  state.autoRefreshTimer = null;
  if (!state.autoRefresh) return;
  state.autoRefreshTimer = window.setInterval(async () => {
    try {
      await refreshDashboard();
      await Promise.all(Object.keys(state.agentLogs).map((agentId) => refreshAgentLogs(agentId)));
      render();
    } catch (error) {
      showError(error.message || String(error));
      render();
    }
  }, 10000);
}

async function main() {
  const defaults = DEFAULT_PREFERENCES;
  const initialLanguage = readPreference(localStorage, STORAGE_KEYS.language, defaults.language);
  const initialTheme = readPreference(localStorage, STORAGE_KEYS.theme, defaults.theme);

  i18n = createI18n({
    document,
    storage: localStorage,
    initialLocale: initialLanguage
  });
  await i18n.init();

  const languageSwitcher = document.querySelector("#language-switcher");

  themeController = createThemeController({
    document,
    storage: localStorage,
    initialMode: initialTheme,
    t: i18n.t
  });
  themeController.bindSwitcher(document.querySelector("#theme-switcher"));

  i18n.bindLanguageSwitcher(languageSwitcher, async () => {
    themeController.bindSwitcher(document.querySelector("#theme-switcher"));
    render();
  });

  bindEvents();
  render();
  await refreshConfig();
  loadDefaultPreferences().then((remoteDefaults) => {
    if (!readPreference(localStorage, STORAGE_KEYS.language, "")) {
      i18n.setLocale(remoteDefaults.language).then(() => render()).catch(() => {});
    }
    if (!readPreference(localStorage, STORAGE_KEYS.theme, "")) {
      themeController.setTheme(remoteDefaults.theme);
      themeController.bindSwitcher(document.querySelector("#theme-switcher"));
    }
  }).catch(() => {});
  if (state.selectedTab === "dashboard") {
    refreshDashboardInBackground();
  } else if (state.selectedTab === "images") {
    refreshDockerImagesInBackground();
  } else if (state.selectedTab === "resources") {
    refreshDockerResourcesInBackground();
  } else {
    window.setTimeout(() => refreshDashboardInBackground(), 250);
    window.setTimeout(() => refreshDockerImagesInBackground(), 500);
  }
}

main().catch((error) => {
  showError(error.message || String(error));
  render();
});
