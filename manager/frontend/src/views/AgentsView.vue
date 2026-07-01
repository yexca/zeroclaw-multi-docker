<template>
  <section class="view-stack">
    <PageHeader :title="t('agents.title')" :description="t('agents.subtitle')">
      <UiButton variant="primary" @click="createAgent"><Plus />{{ t("agents.newAgent") }}</UiButton>
    </PageHeader>

    <div class="agent-workbench">
      <UiCard :title="t('agents.list')" :description="t('agents.listHelp')">
        <div class="item-list">
          <button v-for="agent in store.agents" :key="itemId(agent)" :class="{ active: selectedId === itemId(agent) }" @click="selectAgent(agent)">
            <strong>{{ itemId(agent) }}</strong>
            <span>{{ agent.llm_profile || t("agents.noLlm") }} / {{ agent.matrix_profile || t("agents.noMatrix") }}</span>
          </button>
          <p v-if="!store.agents.length" class="empty-text">{{ t("agents.emptyList") }}</p>
        </div>
      </UiCard>

      <UiCard :title="t('agents.details')" :description="draft?._draft ? t('agents.unsaved') : t('agents.detailsHelp')">
        <form v-if="draft" class="form-grid" @submit.prevent="save">
          <FormField v-model="draft.id" :label="t('agents.agentId')" :error="formErrors.id" required />
          <FormField v-model="draft.host_port" :label="t('fields.hostPort')" type="number" min="1" max="65535" :error="formErrors.host_port" required />
          <FormField v-model="draft.llm_profile" :label="t('fields.llmProfile')" :options="profileOptions('llm')" :error="formErrors.llm_profile" required />
          <FormField v-model="draft.vision_profile" :label="t('fields.visionProfile')" :options="profileOptions('vision', true)" :error="formErrors.vision_profile" />
          <FormField v-model="draft.matrix_profile" :label="t('fields.matrixProfile')" :options="profileOptions('matrix')" :error="formErrors.matrix_profile" required />
          <FormField v-model="draft.mcp_profile" :label="t('fields.mcpProfile')" :options="profileOptions('mcp', true)" :error="formErrors.mcp_profile" />
          <FormField v-model="draft.prompt_template" :label="t('fields.promptTemplate')" :options="templateOptions" :error="formErrors.prompt_template" />
          <FormField v-model="imagePreset" :label="t('fields.imagePreset')" :options="imageOptions" wide />
          <FormField v-model="draft.image" :label="t('fields.dockerImage')" :error="formErrors.image" wide required />
          <FormField v-model="externalPeers" :label="t('fields.externalPeers')" textarea wide />
          <FormField v-model="skillBundles" :label="t('fields.skillBundles')" :error="formErrors.skill_bundles" textarea wide />
          <details class="advanced-disclosure form-field--wide">
            <summary>{{ t("fields.advanced") }}</summary>
            <div class="form-grid nested-form">
              <label class="check-row form-field--wide">
                <input v-model="draft.enabled" type="checkbox" />
                <span>{{ t("fields.enabled") }}</span>
              </label>
              <FormField v-model="draft.template_apply_mode" :label="t('fields.templateApplyMode')" :options="templateModeOptions" />
              <FormField v-model="draft.storage_driver" :label="t('fields.storageDriver')" :options="storageOptions" />
              <FormField v-model="draft.container_name" :label="t('fields.containerName')" :error="formErrors.container_name" />
              <FormField v-model="envOverrides" :label="t('fields.environment')" textarea wide />
            </div>
          </details>
          <details class="advanced-disclosure form-field--wide">
            <summary>{{ t("fields.proactiveSettings") }}</summary>
            <div class="form-grid nested-form">
              <label class="check-row form-field--wide">
                <input v-model="proactive.enabled" type="checkbox" />
                <span>{{ t("fields.enabled") }}</span>
              </label>
              <FormField v-model="proactive.target" :label="t('fields.proactiveTarget')" />
              <FormField v-model="proactive.channel" :label="t('fields.proactiveChannel')" />
              <FormField v-model="proactive.timezone" :label="t('fields.proactiveTimezone')" />
              <FormField v-model="proactive.quiet_hours" :label="t('fields.proactiveQuietHours')" :error="formErrors.proactive_quiet_hours" />
              <FormField v-model="proactive.random_min_minutes" :label="t('fields.proactiveRandomMinMinutes')" type="number" min="1" :error="formErrors.proactive_random_min_minutes" />
              <FormField v-model="proactive.random_max_minutes" :label="t('fields.proactiveRandomMaxMinutes')" type="number" min="1" :error="formErrors.proactive_random_max_minutes" />
              <FormField v-model="proactive.poll_seconds" :label="t('fields.proactivePollSeconds')" type="number" min="30" :error="formErrors.proactive_poll_seconds" />
              <FormField v-model="proactive.agent_url" :label="t('fields.proactiveAgentUrl')" :error="formErrors.proactive_agent_url" />
              <FormField v-model="proactive.prompt" :label="t('agents.wakePrompt')" textarea wide />
            </div>
          </details>
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("actions.save") }}</UiButton>
            <UiButton v-if="!draft._draft" @click="control('start')"><Play />{{ t("actions.start") }}</UiButton>
            <UiButton v-if="!draft._draft" @click="control('stop')"><Square />{{ t("actions.stop") }}</UiButton>
            <UiButton v-if="!draft._draft" @click="control('restart')"><RotateCw />{{ t("actions.restart") }}</UiButton>
            <UiButton v-if="!draft._draft" variant="danger" @click="resetMatrix"><RefreshCcw />{{ t("actions.resetMatrixState") }}</UiButton>
            <UiButton v-if="!draft._draft" variant="danger" @click="remove"><Trash2 />{{ t("actions.delete") }}</UiButton>
          </div>
          <p v-if="formMessage" class="field-error form-field--wide">{{ formMessage }}</p>
        </form>
        <p v-else class="empty-text">{{ t("agents.empty") }}</p>
      </UiCard>

      <UiCard :title="t('agents.runtime')" :description="t('agents.runtimeHelp')">
        <template v-if="draft && !draft._draft">
          <div class="runtime-actions">
            <UiButton @click="loadStatus"><Activity />{{ t("runtimeTabs.status") }}</UiButton>
            <label class="inline-select">
              <span>{{ t("dashboard.tail") }}</span>
              <input v-model.number="logTail" type="number" min="1" max="2000" />
            </label>
            <UiButton @click="loadLogs"><ScrollText />{{ t("runtimeTabs.logs") }}</UiButton>
            <UiButton @click="loadPreview"><FileCode2 />{{ t("runtimeTabs.config") }}</UiButton>
            <UiButton @click="loadEnv"><Braces />{{ t("runtimeTabs.env") }}</UiButton>
            <UiButton @click="downloadLogs"><Download />{{ t("actions.downloadLogs") }}</UiButton>
          </div>
          <div class="runtime-actions">
            <label class="inline-select">
              <span>{{ t("agents.applyMode") }}</span>
              <select v-model="applyTemplateMode">
                <option v-for="option in templateModeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </label>
            <UiButton @click="applyTemplate"><FileCheck2 />{{ t("actions.applyTemplate") }}</UiButton>
            <UiButton @click="runAgentAction('publish')"><Upload />{{ t("actions.publish") }}</UiButton>
            <UiButton @click="runAgentAction('sync-to-runtime')"><ArrowUpFromLine />{{ t("actions.syncToRuntime") }}</UiButton>
            <UiButton @click="runAgentAction('sync-from-runtime')"><ArrowDownToLine />{{ t("actions.syncFromRuntime") }}</UiButton>
          </div>
          <div class="segment-tabs">
            <button v-for="tab in runtimeTabs" :key="tab" :class="{ active: runtimeTab === tab }" @click="runtimeTab = tab">{{ t(`runtimeTabs.${tab}`) }}</button>
          </div>
          <div v-if="runtimeTab === 'status'" class="runtime-summary">
            <div v-for="(value, key) in statusSummary" :key="key">
              <span>{{ key }}</span>
              <strong>{{ value }}</strong>
            </div>
          </div>
          <pre v-else-if="runtimeTab === 'logs'" class="code-block">{{ logsText }}</pre>
          <pre v-else-if="runtimeTab === 'config'" class="code-block">{{ configText }}</pre>
          <pre v-else-if="runtimeTab === 'env'" class="code-block">{{ envText }}</pre>
          <pre v-else class="code-block">{{ resultText }}</pre>
        </template>
        <p v-else class="empty-text">{{ t("agents.saveBeforeRuntime") }}</p>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  Braces,
  Download,
  FileCheck2,
  FileCode2,
  Plus,
  Play,
  RefreshCcw,
  RotateCw,
  Save,
  ScrollText,
  Square,
  Trash2,
  Upload
} from "@lucide/vue";
import FormField from "../components/FormField.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { clone, itemId } from "../lib/api.js";
import { firstError, validateHttpUrl, validateId, validateIntegerRange, validateRequired, valueExists } from "../lib/validation.js";
import { issueMessages, mapIssuesToAgentForm, validationIssuesFromError } from "../lib/validationIssues.mjs";
import { useManagerStore } from "../stores/manager.js";

const route = useRoute();
const router = useRouter();
const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const selectedId = ref("");
const draft = ref(null);
const runtimeTab = ref("status");
const runtimeTabs = ["status", "logs", "config", "env", "result"];
const runtimeStatus = ref(null);
const runtimeLogs = ref(null);
const runtimeConfig = ref(null);
const runtimeEnv = ref(null);
const runtimeResult = ref(null);
const formErrors = ref({});
const formMessage = ref("");
const applyTemplateMode = ref("keep");
const logTail = ref(200);
const DEFAULT_ZEROCLAW_IMAGE = "ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian";
const AGENT_SELECTION_STORAGE_KEY = "zeroclaw.webui.selected.agent";
const templateModeOptions = [
  { label: t("templateApply.keep"), value: "keep" },
  { label: t("templateApply.missing"), value: "missing" },
  { label: t("templateApply.overwrite"), value: "overwrite" },
  { label: t("templateApply.merge"), value: "merge" }
];
const storageOptions = [
  { label: t("common.default"), value: "" },
  { label: t("agents.storage.volume"), value: "volume" },
  { label: t("agents.storage.bind"), value: "bind" }
];

const imageOptions = computed(() => {
  const recommended = store.images?.recommended || {
    official: DEFAULT_ZEROCLAW_IMAGE,
    python: "zeroclaw-python:v0.8.1-debian",
    root: "zeroclaw-root:v0.8.1-debian"
  };
  return [
    { label: t("images.custom"), value: "__custom__" },
    { label: t("images.official"), value: recommended.official },
    { label: t("images.python"), value: recommended.python },
    { label: t("images.root"), value: recommended.root }
  ];
});

const imagePreset = computed({
  get: () => {
    const match = imageOptions.value.find((option) => option.value === draft.value?.image);
    return match ? match.value : "__custom__";
  },
  set: (value) => {
    if (value !== "__custom__") draft.value.image = value;
  }
});

watch(
  () => store.agents,
  (agents) => {
    const routeAgent = queryString(route.query.agent);
    const storedAgent = localStorage.getItem(AGENT_SELECTION_STORAGE_KEY) || "";
    const targetAgent = routeAgent || storedAgent;
    if (targetAgent && agents.some((agent) => itemId(agent) === targetAgent) && selectedId.value !== targetAgent) {
      selectAgent(agents.find((agent) => itemId(agent) === targetAgent), { syncRoute: !routeAgent });
      return;
    }
    if (!draft.value && agents.length) selectAgent(agents[0]);
  },
  { immediate: true }
);

watch(
  () => route.query.agent,
  (agentId) => {
    const agent = store.agents.find((item) => itemId(item) === queryString(agentId));
    if (agent) selectAgent(agent, { syncRoute: false });
  }
);

const externalPeers = computed({
  get: () => (draft.value?.matrix?.external_peers || draft.value?.external_peers || []).join("\n"),
  set: (value) => {
    const peers = value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (!draft.value.matrix) draft.value.matrix = {};
    draft.value.matrix.external_peers = peers;
    delete draft.value.external_peers;
  }
});

const skillBundles = computed({
  get: () => (draft.value?.skill_bundles || []).join("\n"),
  set: (value) => (draft.value.skill_bundles = value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean))
});

const envOverrides = computed({
  get: () => {
    const env = draft.value?.environment || draft.value?.env || {};
    return Object.entries(env).map(([key, value]) => `${key}=${value}`).join("\n");
  },
  set: (value) => {
    draft.value.environment = Object.fromEntries(
      value
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const index = line.indexOf("=");
          return index >= 0 ? [line.slice(0, index).trim(), line.slice(index + 1)] : [line, ""];
        })
    );
  }
});

const proactive = computed({
  get: () => {
    if (!draft.value.proactive) draft.value.proactive = {};
    return draft.value.proactive;
  },
  set: (value) => (draft.value.proactive = value)
});

const templateOptions = computed(() => [
  { label: t("common.none"), value: "" },
  ...store.templates.map((template) => ({ label: itemId(template), value: itemId(template) }))
]);

function profileOptions(kind, optional = false) {
  const values = (store.profiles[kind] || []).map((profile) => ({ label: itemId(profile), value: itemId(profile) }));
  return optional ? [{ label: t("common.none"), value: "" }, ...values] : values;
}

function selectAgent(agent, options = {}) {
  selectedId.value = itemId(agent);
  draft.value = clone(agent);
  localStorage.setItem(AGENT_SELECTION_STORAGE_KEY, selectedId.value);
  if (options.syncRoute !== false) replaceQueryValue("agent", selectedId.value);
  formErrors.value = {};
  formMessage.value = "";
  runtimeStatus.value = null;
  runtimeLogs.value = null;
  runtimeConfig.value = null;
  runtimeEnv.value = null;
  runtimeResult.value = null;
}

function createAgent() {
  draft.value = { ...store.newAgent(), _draft: true };
  selectedId.value = "";
  replaceQueryValue("agent", "");
  formErrors.value = {};
  formMessage.value = "";
}

async function save() {
  if (!validateAgentForm()) return;
  const payload = clone(draft.value);
  delete payload._draft;
  try {
    await store.saveAgent(payload);
    selectedId.value = payload.id;
    draft.value = payload;
    localStorage.setItem(AGENT_SELECTION_STORAGE_KEY, payload.id);
    replaceQueryValue("agent", payload.id);
    formErrors.value = {};
    formMessage.value = "";
  } catch (error) {
    applyBackendValidation(error, payload.id);
  }
}

function applyBackendValidation(error, agentId) {
  const issues = validationIssuesFromError(error);
  if (!issues.length) {
    formMessage.value = error.message || String(error);
    return;
  }
  const mapped = mapIssuesToAgentForm(issues, agentId);
  formErrors.value = { ...formErrors.value, ...mapped.errors };
  const messages = issueMessages(mapped.global);
  formMessage.value = messages.length ? messages.join(" ") : t("validation.fixFields");
}

function validateAgentForm() {
  const errors = {};
  const labels = {
    id: t("agents.agentId"),
    host_port: t("fields.hostPort"),
    llm_profile: t("fields.llmProfile"),
    vision_profile: t("fields.visionProfile"),
    matrix_profile: t("fields.matrixProfile"),
    mcp_profile: t("fields.mcpProfile"),
    prompt_template: t("fields.promptTemplate"),
    skill_bundles: t("fields.skillBundles"),
    image: t("fields.dockerImage"),
    container_name: t("fields.containerName"),
    proactive_quiet_hours: t("fields.proactiveQuietHours"),
    proactive_random_min_minutes: t("fields.proactiveRandomMinMinutes"),
    proactive_random_max_minutes: t("fields.proactiveRandomMaxMinutes"),
    proactive_poll_seconds: t("fields.proactivePollSeconds"),
    proactive_agent_url: t("fields.proactiveAgentUrl")
  };
  validateId(errors, "id", draft.value?.id, t("validation.invalidId", { field: labels.id }));
  if (valueExists(store.agents, draft.value?.id, selectedId.value)) {
    errors.id = t("validation.duplicateValue", { field: labels.id });
  }
  validateIntegerRange(errors, "host_port", draft.value?.host_port, {
    min: 1,
    max: 65535,
    message: t("validation.invalidRange", { field: labels.host_port, min: 1, max: 65535 })
  });
  if (
    Number.isInteger(Number(draft.value?.host_port)) &&
    store.agents.some((agent) => itemId(agent) !== selectedId.value && Number(agent.host_port) === Number(draft.value.host_port))
  ) {
    errors.host_port = t("validation.duplicateValue", { field: labels.host_port });
  }
  validateRequired(errors, "llm_profile", draft.value?.llm_profile, t("messages.requiredField", { field: labels.llm_profile }));
  validateRequired(errors, "matrix_profile", draft.value?.matrix_profile, t("messages.requiredField", { field: labels.matrix_profile }));
  validateKnownProfile(errors, "llm_profile", "llm", labels.llm_profile);
  validateKnownProfile(errors, "matrix_profile", "matrix", labels.matrix_profile);
  validateKnownProfile(errors, "vision_profile", "vision", labels.vision_profile, true);
  validateKnownProfile(errors, "mcp_profile", "mcp", labels.mcp_profile, true);
  if (draft.value?.prompt_template && !store.templates.some((template) => itemId(template) === draft.value.prompt_template)) {
    errors.prompt_template = t("validation.unknownReference", { field: labels.prompt_template });
  }
  const knownBundles = new Set(store.skillBundles.map((bundle) => itemId(bundle)));
  const missingBundles = (draft.value?.skill_bundles || []).filter((bundle) => !knownBundles.has(bundle));
  if (missingBundles.length) errors.skill_bundles = t("validation.unknownReference", { field: labels.skill_bundles });
  validateRequired(errors, "image", draft.value?.image, t("messages.requiredField", { field: labels.image }));
  if (draft.value?.container_name) validateId(errors, "container_name", draft.value.container_name, t("validation.invalidId", { field: labels.container_name }));

  const proactiveDraft = draft.value?.proactive || {};
  if (proactiveDraft.enabled) {
    validateIntegerRange(errors, "proactive_random_min_minutes", proactiveDraft.random_min_minutes, {
      min: 1,
      message: t("messages.invalidMinNumberField", { field: labels.proactive_random_min_minutes, min: 1 })
    });
    validateIntegerRange(errors, "proactive_random_max_minutes", proactiveDraft.random_max_minutes, {
      min: 1,
      message: t("messages.invalidMinNumberField", { field: labels.proactive_random_max_minutes, min: 1 })
    });
    validateIntegerRange(errors, "proactive_poll_seconds", proactiveDraft.poll_seconds, {
      min: 30,
      message: t("messages.invalidMinNumberField", { field: labels.proactive_poll_seconds, min: 30 })
    });
    if (Number(proactiveDraft.random_max_minutes) < Number(proactiveDraft.random_min_minutes)) {
      errors.proactive_random_max_minutes = t("messages.invalidMinNumberField", {
        field: labels.proactive_random_max_minutes,
        min: proactiveDraft.random_min_minutes
      });
    }
    if (proactiveDraft.quiet_hours && !/^(?:[01]?\d|2[0-3])-(?:[01]?\d|2[0-3])$/.test(String(proactiveDraft.quiet_hours).trim())) {
      errors.proactive_quiet_hours = t("validation.invalidQuietHours", { field: labels.proactive_quiet_hours });
    }
    validateHttpUrl(errors, "proactive_agent_url", proactiveDraft.agent_url, t("messages.invalidUrlField", { field: labels.proactive_agent_url }));
  }

  formErrors.value = errors;
  formMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  return !formMessage.value;
}

function validateKnownProfile(errors, key, kind, label, optional = false) {
  const value = draft.value?.[key];
  if (optional && !value) return;
  if (!value || errors[key]) return;
  if (!(store.profiles[kind] || []).some((profile) => itemId(profile) === value)) {
    errors[key] = t("validation.unknownReference", { field: label });
  }
}

async function remove() {
  if (!draft.value?._draft && await dialog.confirm(t("confirm.deleteAgentNamed", { id: draft.value.id }))) {
    await store.deleteAgent(draft.value.id);
    localStorage.removeItem(AGENT_SELECTION_STORAGE_KEY);
    replaceQueryValue("agent", "");
    draft.value = null;
    selectedId.value = "";
  }
}

function queryString(value) {
  return Array.isArray(value) ? String(value[0] || "") : String(value || "");
}

function replaceQueryValue(key, value) {
  const query = { ...route.query };
  if (value) query[key] = value;
  else delete query[key];
  router.replace({ query }).catch(() => {});
}

const statusSummary = computed(() => {
  const status = runtimeStatus.value || {};
  return {
    state: status.state || status.status || t("common.unknown"),
    health: status.health || "-",
    image: status.image || draft.value?.image || "-",
    mapped_port: status.mapped_port || status.port || draft.value?.host_port || "-",
    config_hash: status.config_hash || "-",
    latest_export: status.latest_export_time || "-"
  };
});

const logsText = computed(() => {
  if (!runtimeLogs.value) return t("dashboard.logsEmpty");
  return (runtimeLogs.value.lines || []).join("\n") || JSON.stringify(runtimeLogs.value, null, 2);
});

const configText = computed(() => formatRuntime(runtimeConfig.value, t("agents.noConfigPreview")));
const envText = computed(() => formatRuntime(runtimeEnv.value, t("agents.noEnvPreview")));
const resultText = computed(() => formatRuntime(runtimeResult.value, t("agents.noActionResult")));

function formatRuntime(value, empty) {
  if (!value) return empty;
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function loadStatus() {
  runtimeStatus.value = await store.getAgentStatus(draft.value.id);
  runtimeTab.value = "status";
}

async function loadLogs() {
  runtimeLogs.value = await store.getAgentLogs(draft.value.id, logTail.value);
  runtimeTab.value = "logs";
}

async function loadPreview() {
  runtimeConfig.value = await store.getAgentPreview(draft.value.id);
  runtimeTab.value = "config";
}

async function loadEnv() {
  runtimeEnv.value = await store.getAgentEnv(draft.value.id);
  runtimeTab.value = "env";
}

async function runAgentAction(action) {
  runtimeResult.value = await store.agentAction(draft.value.id, action);
  runtimeTab.value = "result";
  await loadStatus();
}

async function applyTemplate() {
  runtimeResult.value = await store.agentAction(draft.value.id, "apply-template", { mode: applyTemplateMode.value });
  runtimeTab.value = "result";
  await loadStatus();
}

async function control(operation) {
  await store.controlAgent(draft.value.id, operation);
  await loadStatus();
  if (operation !== "stop") await loadLogs();
}

function downloadLogs() {
  window.location.href = store.agentLogsDownloadUrl(draft.value.id, logTail.value);
}

async function resetMatrix() {
  if (!(await dialog.confirm(t("confirm.resetMatrixStateNamed", { id: draft.value.id })))) return;
  await runAgentAction("reset-matrix-state");
}

onMounted(() => {
  if (!store.images) store.loadImages().catch((error) => store.setError(error));
});
</script>
