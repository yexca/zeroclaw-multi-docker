import { createI18n } from "./i18n.mjs";
import { loadDefaultPreferences, readPreference, STORAGE_KEYS } from "./preferences.mjs";
import { createThemeController } from "./theme.mjs";

const TEMPLATE_FILES = ["AGENTS.md", "IDENTITY.md", "SOUL.md", "MEMORY.md", "TOOLS.md", "USER.md", "HEARTBEAT.md"];
const TABS = ["dashboard", "agents", "llm", "matrix", "mcp", "prompts", "export"];
const SECRET_KEYS = ["api_key", "token", "password", "recovery_key", "secret"];
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
  selectedTab: "dashboard",
  selectedAgentId: "",
  selectedTemplateId: "",
  dashboard: null,
  agentStatuses: {},
  agentLogs: {},
  logTail: 200,
  autoRefresh: false,
  autoRefreshTimer: null,
  busy: false,
  notice: "",
  error: "",
  exportResult: null,
  validationResult: null,
  dashboardLoading: false
};

let i18n;
let themeController;

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
    overrides: t("fields.overrides"),
    id: t("fields.id"),
    name: t("fields.name"),
    host_port: t("fields.hostPort"),
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
    url: t("fields.url")
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
  window.alert(error.message || String(error));
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

async function runAction(action, successKey) {
  try {
    setBusy(true);
    state.error = "";
    state.notice = "";
    const result = await action();
    state.notice = successKey ? t(successKey) : "";
    await refreshConfig(false);
    return result;
  } catch (error) {
    state.error = error.message || String(error);
    return null;
  } finally {
    state.busy = false;
    render();
  }
}

async function refreshConfig(shouldRender = true) {
  state.config = await api("/api/config");
  state.selectedAgentId = selectedAgent() ? itemId(selectedAgent()) : "";
  state.selectedTemplateId = selectedTemplate() ? itemId(selectedTemplate()) : "";
  if (shouldRender) render();
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

async function refreshDashboardInBackground() {
  state.dashboardLoading = true;
  render();
  try {
    await refreshDashboard();
    state.error = "";
  } catch (error) {
    state.error = error.message || String(error);
  } finally {
    state.dashboardLoading = false;
    render();
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

function llmFamily(item) {
  return item.provider_family || item.family || item.kind || "openai";
}

function createLlmProfile(id) {
  return { id, ...LLM_PRESETS.openai, _draft: true };
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

function actionButton(action, labelKey, variant = "secondary", disabled = false) {
  return `<button type="button" class="button ${variant}" data-action="${action}" ${disabled ? "disabled" : ""}>${escapeHtml(
    t(labelKey)
  )}</button>`;
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
  `;
}

function renderNotices() {
  const loading =
    state.busy || state.dashboardLoading ? `<div class="notice muted">${escapeHtml(t("common.loading"))}</div>` : "";
  const notice = state.notice ? `<div class="notice success">${escapeHtml(state.notice)}</div>` : "";
  const error = state.error ? `<div class="notice danger">${escapeHtml(state.error)}</div>` : "";
  return `${loading}${notice}${error}`;
}

function renderSelectedTab() {
  if (!state.config) return `<div class="empty-state">${escapeHtml(t("common.loading"))}</div>`;
  if (state.selectedTab === "dashboard") return renderDashboard();
  if (state.selectedTab === "agents") return renderAgentEditor();
  if (state.selectedTab === "llm") return renderProfileManager("llm");
  if (state.selectedTab === "matrix") return renderProfileManager("matrix");
  if (state.selectedTab === "mcp") return renderProfileManager("mcp");
  if (state.selectedTab === "prompts") return renderPromptTemplates();
  if (state.selectedTab === "export") return renderExport();
  return "";
}

function renderDashboard() {
  const agents = collection("agents");
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
        agents.length
          ? agents.map(renderAgentCard).join("")
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
  return `
    <article class="agent-card">
      <header class="card-header">
        <div>
          <h3>${escapeHtml(id || t("common.unnamed"))}</h3>
          <p>${escapeHtml(agent.enabled === false ? t("common.disabled") : t("common.enabled"))}</p>
        </div>
        <span class="status-pill state-${escapeHtml(status?.normalized_state || status?.state || "unknown")}">${escapeHtml(
          status?.normalized_state || status?.state || t("common.unknown")
        )}</span>
      </header>
      <dl class="data-list">
        <div><dt>${escapeHtml(t("fields.hostPort"))}</dt><dd>${escapeHtml(agent.host_port || "")}</dd></div>
        <div><dt>${escapeHtml(t("observability.containerId"))}</dt><dd>${escapeHtml(shortHash(status?.container_id))}</dd></div>
        <div><dt>${escapeHtml(t("observability.image"))}</dt><dd>${escapeHtml(status?.image || agent.image || "")}</dd></div>
        <div><dt>${escapeHtml(t("observability.created"))}</dt><dd>${escapeHtml(formatDate(status?.created_at))}</dd></div>
        <div><dt>${escapeHtml(t("observability.started"))}</dt><dd>${escapeHtml(formatDate(status?.started_at))}</dd></div>
        <div><dt>${escapeHtml(t("observability.health"))}</dt><dd>${escapeHtml(status?.health_status || "")}</dd></div>
        <div><dt>${escapeHtml(t("observability.restartCount"))}</dt><dd>${escapeHtml(status?.restart_count ?? "")}</dd></div>
        <div><dt>${escapeHtml(t("observability.mappedPort"))}</dt><dd>${escapeHtml(status?.mapped_port || "")}</dd></div>
        <div><dt>${escapeHtml(t("observability.configHash"))}</dt><dd>${escapeHtml(shortHash(status?.config_hash))}</dd></div>
        <div><dt>${escapeHtml(t("observability.containerHash"))}</dt><dd>${escapeHtml(shortHash(status?.container_config_hash))}</dd></div>
        <div><dt>${escapeHtml(t("observability.rebuild"))}</dt><dd>${escapeHtml(status?.needs_rebuild ? t("common.yes") : t("common.no"))}</dd></div>
        <div><dt>${escapeHtml(t("observability.latestExport"))}</dt><dd>${escapeHtml(formatDate(status?.latest_export_time))}</dd></div>
        <div><dt>${escapeHtml(t("fields.model"))}</dt><dd>${escapeHtml(agent.model?.model || agent.llm_profile || "")}</dd></div>
        <div><dt>${escapeHtml(t("fields.matrixUser"))}</dt><dd>${escapeHtml(agent.matrix?.user_id || "")}</dd></div>
        <div><dt>${escapeHtml(t("fields.mcpStatus"))}</dt><dd>${escapeHtml(agent.mcp_profile || t("common.none"))}</dd></div>
      </dl>
      <div class="button-row">
        ${actionButton(`agent-start:${id}`, "actions.start", "primary")}
        ${actionButton(`agent-stop:${id}`, "actions.stop")}
        ${actionButton(`agent-restart:${id}`, "actions.restart")}
        ${actionButton(`agent-logs:${id}`, "actions.logs")}
        ${actionButton(`agent-download-logs:${id}`, "actions.downloadLogs")}
        ${actionButton(`agent-edit:${id}`, "actions.edit")}
        ${actionButton(`agent-delete:${id}`, "actions.delete", "danger")}
      </div>
      <pre class="log-viewer">${escapeHtml(formatLogs(logs, status))}</pre>
    </article>
  `;
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
      <div class="button-row">
        ${actionButton("agent-new", "actions.create", "primary")}
        ${actionButton("agent-duplicate", "actions.duplicate", "secondary", !agent)}
        ${actionButton("agent-delete-current", "actions.delete", "danger", !agent)}
      </div>
    </header>
    <div class="split">
      <aside class="list-panel">${renderItemList("agents", collection("agents"), state.selectedAgentId)}</aside>
      <form class="form-panel" data-form="agent">${agent ? renderAgentForm(agent) : renderEmptyEditor("agents.empty")}</form>
    </div>
  `;
}

function renderItemList(kind, items, selectedId) {
  if (!items.length) return `<div class="empty-state">${escapeHtml(t("common.empty"))}</div>`;
  return items
    .map((item) => {
      const id = itemId(item);
      const modelTag = kind === "llm" && item.model ? `<span class="list-tag">${escapeHtml(item.model)}</span>` : "";
      return `<button type="button" class="list-item ${id === selectedId ? "active" : ""}" data-select-${kind}="${escapeHtml(
        id
      )}"><span class="list-item-main">${escapeHtml(id)}</span>${modelTag}</button>`;
    })
    .join("");
}

function renderAgentForm(agent) {
  const matrix = agent.matrix || {};
  return `
    <div class="form-grid">
      ${field("fields.id", "id", itemId(agent), "required")}
      ${field("fields.name", "name", agent.name || "")}
      ${field("fields.hostPort", "host_port", agent.host_port || "", 'type="number" min="1" max="65535"')}
      ${field("fields.image", "image", agent.image || "")}
      ${checkboxField("fields.enabled", "enabled", agent.enabled !== false)}
      ${selectField("fields.llmProfile", "llm_profile", optionList(collection("llm"), agent.llm_profile, "common.none"))}
      ${selectField("fields.matrixProfile", "matrix_profile", optionList(collection("matrix"), agent.matrix_profile, "common.none"))}
      ${selectField("fields.mcpProfile", "mcp_profile", optionList(collection("mcp"), agent.mcp_profile, "common.none"))}
      ${selectField(
        "fields.promptTemplate",
        "prompt_template",
        optionList(collection("prompt_templates"), agent.prompt_template, "common.none")
      )}
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
          .join("")
      )}
      ${field("fields.matrixUser", "matrix_user_id", matrix.user_id || "")}
      ${field("fields.deviceId", "matrix_device_id", matrix.device_id || "")}
      ${passwordField("fields.accessToken", "matrix_access_token", matrix.access_token || "")}
      ${passwordField("fields.password", "matrix_password", matrix.password || "")}
      ${passwordField("fields.recoveryKey", "matrix_recovery_key", matrix.recovery_key || "")}
      ${textareaField("fields.externalPeers", "matrix_external_peers", asLines(matrix.external_peers))}
      ${textareaField("fields.overrides", "overrides", JSON.stringify(agent.overrides || {}, null, 2))}
    </div>
    <div class="button-row form-actions">
      ${actionButton("agent-save", "actions.save", "primary")}
      ${actionButton("agent-validate", "actions.validate")}
      ${actionButton("agent-apply-template", "actions.applyTemplate", "secondary", !agent.prompt_template)}
    </div>
    ${renderValidation()}
  `;
}

function renderValidation() {
  if (!state.validationResult) return "";
  const errors = state.validationResult.errors || [];
  const warnings = state.validationResult.warnings || [];
  return `<div class="result-box">
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
      <div class="button-row">
        ${actionButton(`${kind}-new`, "actions.create", "primary")}
        ${actionButton(`${kind}-delete-current`, "actions.delete", "danger", !selected)}
      </div>
    </header>
    <div class="split">
      <aside class="list-panel">${renderItemList(kind, items, state[`selected${kind}Id`])}</aside>
      <form class="form-panel" data-form="${kind}">${selected ? renderProfileForm(kind, selected) : renderEmptyEditor(`${kind}.empty`)}</form>
    </div>
  `;
}

function renderProfileForm(kind, item) {
  if (kind === "llm") {
    const profile = applyLlmPresetToEmptyFields(item, llmFamily(item));
    const family = llmFamily(profile);
    return `
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

function renderPromptTemplates() {
  const template = selectedTemplate();
  return `
    <header class="section-header">
      <div><h2>${escapeHtml(t("prompts.title"))}</h2><p>${escapeHtml(t("prompts.subtitle"))}</p></div>
      <div class="button-row">
        ${actionButton("template-new", "actions.create", "primary")}
        ${actionButton("template-duplicate", "actions.duplicate", "secondary", !template)}
        ${actionButton("template-delete-current", "actions.delete", "danger", !template)}
      </div>
    </header>
    <div class="split wide">
      <aside class="list-panel">${renderItemList("templates", collection("prompt_templates"), state.selectedTemplateId)}</aside>
      <form class="form-panel" data-form="template">${template ? renderTemplateForm(template) : renderEmptyEditor("prompts.empty")}</form>
    </div>
  `;
}

function renderTemplateForm(template) {
  const files = template.files && !Array.isArray(template.files) ? template.files : {};
  return `
    <div class="form-grid">
      ${field("fields.id", "id", itemId(template), "required")}
      ${field("fields.description", "description", template.description || "")}
      ${TEMPLATE_FILES.map((file) => textareaField(file, `file:${file}`, files[file] || "", 'class="template-text"')).join("")}
    </div>
    <div class="button-row form-actions">${actionButton("template-save", "actions.save", "primary")}</div>
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
    compose_services: agents.map((agent) => itemId(agent)),
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
  return {
    ...current,
    id: requireString(data, "id"),
    name: String(data.get("name") || "").trim(),
    enabled: data.get("enabled") === "on",
    host_port: requireNumber(data, "host_port", { min: 1, max: 65535 }),
    image: String(data.get("image") || "").trim(),
    llm_profile: String(data.get("llm_profile") || ""),
    matrix_profile: String(data.get("matrix_profile") || ""),
    mcp_profile: String(data.get("mcp_profile") || ""),
    prompt_template: String(data.get("prompt_template") || ""),
    template_apply_mode: String(data.get("template_apply_mode") || "keep"),
    matrix: {
      ...matrix,
      user_id: String(data.get("matrix_user_id") || ""),
      device_id: String(data.get("matrix_device_id") || ""),
      access_token: keepSecret(data, "matrix_access_token", matrix.access_token),
      password: keepSecret(data, "matrix_password", matrix.password),
      recovery_key: keepSecret(data, "matrix_recovery_key", matrix.recovery_key),
      external_peers: fromLines(String(data.get("matrix_external_peers") || ""))
    },
    overrides: readJsonField(data, "overrides", {})
  };
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
  const files = {};
  TEMPLATE_FILES.forEach((file) => {
    files[file] = String(data.get(`file:${file}`) || "");
  });
  return {
    ...current,
    id: String(data.get("id") || "").trim(),
    description: String(data.get("description") || ""),
    files
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
  return window.confirm(t(messageKey));
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

  if (action === "refresh-all-status") {
    return runAction(async () => {
      await refreshDashboard();
      await Promise.all(collection("agents").map((agent) => refreshAgentLogs(itemId(agent))));
    });
  }
  if (action === "agent-new") {
    state.selectedAgentId = "";
    state.config.agents.unshift({ id: nextId("agent", collection("agents")), enabled: true, matrix: {}, overrides: {}, _draft: true });
    state.selectedAgentId = itemId(state.config.agents[0]);
    render();
  }
  if (action === "agent-duplicate") {
    const source = selectedAgent();
    if (!source) return;
    const copy = cloneData(source);
    copy.id = nextId(`${itemId(source)}-copy`, collection("agents"));
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
    return runAction(async () => {
      state.validationResult = await api(`/api/agents/${encodeURIComponent(id)}/validate`, { method: "POST", body: "{}" });
    });
  }
  if (action === "agent-apply-template") {
    const agent = selectedAgent();
    if (!agent) return;
    const form = document.querySelector('[data-form="agent"]');
    const mode = String(new FormData(form).get("template_apply_mode") || "keep");
    if (mode === "overwrite" && !(await confirmDanger("confirm.overwriteWorkspace"))) return;
    return runAction(
      async () =>
        api(`/api/agents/${encodeURIComponent(itemId(agent))}/apply-template`, {
          method: "POST",
          body: JSON.stringify({ mode })
        }),
      "messages.templateApplied"
    );
  }
  if (action === "agent-delete-current") return deleteAgent(state.selectedAgentId);

  for (const kind of ["llm", "matrix", "mcp"]) {
    if (action === `${kind}-new`) {
      const item = kind === "llm" ? createLlmProfile(nextId(kind, collection(kind))) : { id: nextId(kind, collection(kind)), _draft: true };
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
    const template = { id: nextId("template", collection("prompt_templates")), files: {}, _draft: true };
    state.config.prompt_templates.unshift(template);
    state.selectedTemplateId = template.id;
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
    render();
  }
  if (action === "template-save") {
    const template = templateFromForm(document.querySelector('[data-form="template"]'));
    return runAction(async () => {
      await saveTemplate(state.selectedTemplateId, template);
      state.selectedTemplateId = itemId(template);
    }, "messages.saved");
  }
  if (action === "template-delete-current") return deleteTemplate(state.selectedTemplateId);
  if (action === "config-export") {
    return runAction(async () => {
      state.exportResult = await api("/api/export", { method: "POST", body: JSON.stringify({ filename: "resolved.yaml" }) });
    }, "messages.exported");
  }
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
    state.config.agents = state.config.agents.filter((agent) => itemId(agent) !== agentId);
    state.selectedAgentId = "";
    render();
    return;
  }
  return runAction(async () => {
    await api(`/api/agents/${encodeURIComponent(agentId)}`, { method: "DELETE" });
    state.selectedAgentId = "";
  }, "messages.deleted");
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

function bindEvents() {
  document.addEventListener("click", async (event) => {
    const tab = event.target.closest("[data-tab]")?.dataset.tab;
    if (tab) {
      state.selectedTab = tab;
      state.error = "";
      state.notice = "";
      render();
      return;
    }

    for (const kind of ["agents", "llm", "matrix", "mcp", "templates"]) {
      const selector = event.target.closest(`[data-select-${kind}]`);
      if (selector) {
        const value = selector.dataset[`select${kind[0].toUpperCase()}${kind.slice(1)}`];
        if (kind === "agents") state.selectedAgentId = value;
        else if (kind === "templates") state.selectedTemplateId = value;
        else state[`selected${kind}Id`] = value;
        state.validationResult = null;
        render();
        return;
      }
    }

    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action) await handleAction(action);
  });

  document.addEventListener("submit", (event) => event.preventDefault());

  document.addEventListener("change", (event) => {
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
      state.error = error.message || String(error);
      render();
    }
  }, 10000);
}

async function main() {
  const defaults = await loadDefaultPreferences();
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
  refreshDashboardInBackground();
}

main().catch((error) => {
  state.error = error.message || String(error);
  render();
});
