import { createI18n } from "./i18n.mjs";
import { loadDefaultPreferences, readPreference, STORAGE_KEYS } from "./preferences.mjs";
import { createThemeController } from "./theme.mjs";

const TEMPLATE_FILES = ["AGENTS.md", "IDENTITY.md", "SOUL.md", "MEMORY.md", "TOOLS.md", "USER.md", "HEARTBEAT.md"];
const TABS = ["dashboard", "agents", "llm", "matrix", "mcp", "prompts", "export"];
const SECRET_KEYS = ["api_key", "token", "password", "recovery_key", "secret"];

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
  validationResult: null
};

let i18n;
let themeController;

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

function parseJson(value, fallback = {}) {
  if (!value.trim()) return fallback;
  return JSON.parse(value);
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

function optionList(items, selected, emptyKey) {
  const empty = emptyKey ? `<option value="">${escapeHtml(t(emptyKey))}</option>` : "";
  return `${empty}${items
    .map((item) => {
      const id = itemId(item);
      return `<option value="${escapeHtml(id)}" ${id === selected ? "selected" : ""}>${escapeHtml(id)}</option>`;
    })
    .join("")}`;
}

function field(labelKey, name, value = "", attrs = "") {
  return `<label class="field"><span>${escapeHtml(t(labelKey))}</span><input name="${name}" value="${escapeHtml(
    value
  )}" ${attrs} /></label>`;
}

function passwordField(labelKey, name, value = "") {
  return field(labelKey, name, value ? "••••••••" : "", `type="password" autocomplete="new-password" data-secret="true"`);
}

function textareaField(labelKey, name, value = "", attrs = "") {
  return `<label class="field field-wide"><span>${escapeHtml(t(labelKey))}</span><textarea name="${name}" ${attrs}>${escapeHtml(
    value
  )}</textarea></label>`;
}

function checkboxField(labelKey, name, checked = false) {
  return `<label class="check-field"><input type="checkbox" name="${name}" ${checked ? "checked" : ""} /><span>${escapeHtml(
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

function selectField(labelKey, name, optionsHtml) {
  return `<label class="field"><span>${escapeHtml(t(labelKey))}</span><select name="${name}">${optionsHtml}</select></label>`;
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
  const loading = state.busy ? `<div class="notice muted">${escapeHtml(t("common.loading"))}</div>` : "";
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
      return `<button type="button" class="list-item ${id === selectedId ? "active" : ""}" data-select-${kind}="${escapeHtml(
        id
      )}">${escapeHtml(id)}</button>`;
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
    return `
      <div class="form-grid">
        ${field("fields.id", "id", itemId(item), "required")}
        ${field("fields.kind", "kind", item.kind || item.provider_family || "")}
        ${field("fields.baseUrl", "base_url", item.base_url || "")}
        ${field("fields.model", "model", item.model || "")}
        ${field("fields.wireApi", "wire_api", item.wire_api || "chat_completions")}
        ${field("fields.timeout", "timeout_secs", item.timeout_secs || item.timeout || "", 'type="number" min="1"')}
        ${passwordField("fields.apiKey", "api_key", item.api_key || "")}
      </div>
      <div class="button-row form-actions">${actionButton("profile-save", "actions.save", "primary")}</div>
    `;
  }
  if (kind === "matrix") {
    return `
      <div class="form-grid">
        ${field("fields.id", "id", itemId(item), "required")}
        ${field("fields.homeserver", "homeserver", item.homeserver || "")}
        ${textareaField("fields.allowedRooms", "allowed_rooms", asLines(item.allowed_rooms))}
        ${checkboxField("fields.mentionOnly", "mention_only", item.mention_only === true)}
        ${checkboxField("fields.replyInThread", "reply_in_thread", item.reply_in_thread !== false)}
        ${checkboxField("fields.ackReactions", "ack_reactions", item.ack_reactions !== false)}
        ${field("fields.streamMode", "stream_mode", item.stream_mode || "off")}
      </div>
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
    id: String(data.get("id") || "").trim(),
    name: String(data.get("name") || "").trim(),
    enabled: data.get("enabled") === "on",
    host_port: parseNumber(data.get("host_port"), current.host_port || 0),
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
    overrides: parseJson(String(data.get("overrides") || ""), {})
  };
}

function profileFromForm(kind, form) {
  const data = readForm(form);
  const current = collection(kind).find((item) => itemId(item) === state[`selected${kind}Id`]) || {};
  const base = { ...current, id: String(data.get("id") || "").trim() };
  if (kind === "llm") {
    return {
      ...base,
      kind: String(data.get("kind") || ""),
      base_url: String(data.get("base_url") || ""),
      model: String(data.get("model") || ""),
      wire_api: String(data.get("wire_api") || ""),
      timeout_secs: parseNumber(data.get("timeout_secs"), current.timeout_secs || 0),
      api_key: keepSecret(data, "api_key", current.api_key)
    };
  }
  if (kind === "matrix") {
    return {
      ...base,
      homeserver: String(data.get("homeserver") || ""),
      allowed_rooms: fromLines(String(data.get("allowed_rooms") || "")),
      mention_only: data.get("mention_only") === "on",
      reply_in_thread: data.get("reply_in_thread") === "on",
      ack_reactions: data.get("ack_reactions") === "on",
      stream_mode: String(data.get("stream_mode") || "off")
    };
  }
  return {
    ...base,
    server_name: String(data.get("server_name") || ""),
    transport: String(data.get("transport") || ""),
    url: String(data.get("url") || ""),
    token: keepSecret(data, "token", current.token),
    timeout_secs: parseNumber(data.get("timeout_secs"), current.timeout_secs || 0),
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
    const item = agentFromForm(document.querySelector('[data-form="agent"]'));
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
      const item = { id: nextId(kind, collection(kind)) };
      item._draft = true;
      state.config.profiles[kind].unshift(item);
      state[`selected${kind}Id`] = item.id;
      render();
    }
    if (action === `${kind}-delete-current`) return deleteProfile(kind, state[`selected${kind}Id`]);
  }
  if (action === "profile-save") {
    const kind = document.querySelector(".form-panel")?.dataset.form;
    const item = profileFromForm(kind, document.querySelector(`[data-form="${kind}"]`));
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
  });
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
  await refreshConfig();
  await refreshDashboard();
  render();
}

main().catch((error) => {
  state.error = error.message || String(error);
  render();
});
