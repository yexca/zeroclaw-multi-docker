<template>
  <section class="view-stack">
    <PageHeader :title="title" :description="description">
      <UiButton variant="primary" @click="createProfile"><Plus />{{ t("profiles.newProfile") }}</UiButton>
    </PageHeader>

    <div class="editor-layout">
      <UiCard class="sticky-panel" :title="t('profiles.title')" :description="t('profiles.listHelp')">
        <div class="item-list">
          <button
            v-for="profile in profiles"
            :key="itemId(profile)"
            class="profile-list-item"
            :class="{ active: selectedId === itemId(profile) }"
            @click="selectProfile(profile)"
          >
            <span>
              <strong>{{ itemId(profile) }}</strong>
              <small>{{ profile.model || profile.homeserver || profile.url || profile.provider_family || t("profiles.profile") }}</small>
            </span>
            <mark :class="profileUsage(itemId(profile)).length ? 'good' : ''">
              {{ profileUsage(itemId(profile)).length ? t("profiles.usedCount", { count: profileUsage(itemId(profile)).length }) : t("common.unused") }}
            </mark>
          </button>
          <p v-if="!profiles.length" class="empty-text">{{ t("profiles.emptyList") }}</p>
        </div>
      </UiCard>

      <UiCard :title="t('profiles.details')" :description="t('profiles.detailsHelp')">
        <section v-if="draft" class="profile-usage-panel">
          <div>
            <strong>{{ t("profiles.usedBy") }}</strong>
            <span>{{ currentUsage.length ? t("profiles.agentCount", { count: currentUsage.length }) : t("profiles.noUsage") }}</span>
          </div>
          <div v-if="currentUsage.length" class="file-chip-grid">
            <button v-for="usage in currentUsage" :key="`${usage.id}-${usage.field}`" class="file-chip profile-usage-chip" type="button">
              {{ usage.id }} / {{ usage.field }}
            </button>
          </div>
        </section>
        <form v-if="draft" class="form-grid" @submit.prevent="save">
          <FormField v-model="draft.id" :label="t('fields.id')" :error="formErrors.id" required />
          <template v-if="kind === 'llm' || kind === 'vision'">
            <FormField v-model="draft.provider_family" :label="t('fields.provider')" :error="formErrors.provider_family" required />
            <FormField v-model="draft.provider_alias" :label="t('fields.providerAlias')" :error="formErrors.provider_alias" required />
            <FormField v-model="draft.model" :label="t('fields.model')" :error="formErrors.model" required />
            <FormField v-model="draft.base_url" :label="t('fields.baseUrl')" :error="formErrors.base_url" />
            <FormField v-model="draft.api_key" :label="t('fields.apiKey')" type="password" :error="formErrors.api_key" />
            <FormField v-model="draft.wire_api" :label="t('fields.wireApi')" :options="wireOptions" />
            <FormField v-model="draft.timeout_secs" :label="t('fields.timeout')" type="number" min="1" :error="formErrors.timeout_secs" />
            <template v-if="kind === 'vision'">
              <details class="advanced-disclosure form-field--wide">
                <summary>{{ t("fields.multimodalLimits") }}</summary>
                <div class="form-grid nested-form">
                  <FormField v-model="draft.max_images" :label="t('fields.maxImages')" type="number" min="1" max="16" :error="formErrors.max_images" />
                  <FormField v-model="draft.max_image_size_mb" :label="t('fields.maxImageSizeMb')" type="number" min="1" max="20" :error="formErrors.max_image_size_mb" />
                  <FormField v-model="draft.max_image_turns" :label="t('fields.maxImageTurns')" type="number" min="0" :error="formErrors.max_image_turns" />
                  <label class="check-row form-field--wide">
                    <input v-model="draft.allow_remote_fetch" type="checkbox" />
                    <span>{{ t("fields.allowRemoteFetch") }}</span>
                  </label>
                </div>
              </details>
            </template>
            <template v-else>
              <details class="advanced-disclosure form-field--wide">
                <summary>{{ t("profiles.llmAdvanced") }}</summary>
                <div class="form-grid nested-form">
                  <FormField v-model="draft.temperature" :label="t('fields.temperature')" type="number" min="0" max="2" :error="formErrors.temperature" />
                  <FormField v-model="draft.max_tokens" :label="t('fields.maxTokens')" type="number" min="1" :error="formErrors.max_tokens" />
                  <FormField v-model="fallbackModels" :label="t('fields.fallbackModels')" textarea wide />
                  <FormField v-model="extraHeaders" :label="t('fields.extraHeaders')" textarea wide />
                  <FormField v-model="providerExtra" :label="t('fields.providerExtra')" textarea wide />
                  <FormField v-model="pricing" :label="t('fields.pricing')" textarea wide />
                  <label class="check-row form-field--wide">
                    <input v-model="draft.requires_openai_auth" type="checkbox" />
                    <span>{{ t("fields.requiresOpenaiAuth") }}</span>
                  </label>
                  <label class="check-row form-field--wide">
                    <input v-model="draft.merge_system_into_user" type="checkbox" />
                    <span>{{ t("fields.mergeSystemIntoUser") }}</span>
                  </label>
                </div>
              </details>
            </template>
          </template>
          <template v-else-if="kind === 'matrix'">
            <FormField v-model="draft.homeserver" :label="t('fields.homeserver')" :error="formErrors.homeserver" required />
            <FormField v-model="matrixLoginMode" :label="t('fields.matrixLoginMode')" :options="matrixLoginModeOptions" />
            <template v-if="matrixLoginMode === 'token' || matrixLoginMode === 'advanced'">
              <FormField v-model="draft.device_id" :label="t('fields.deviceId')" :error="formErrors.device_id" required />
              <FormField v-model="draft.access_token" :label="t('fields.accessToken')" type="password" :error="formErrors.access_token" required />
            </template>
            <template v-if="matrixLoginMode === 'account' || matrixLoginMode === 'advanced'">
              <FormField v-model="draft.user_id" :label="t('fields.matrixUser')" :error="formErrors.user_id" required />
              <FormField v-model="draft.password" :label="t('fields.password')" type="password" :error="formErrors.password" required />
              <FormField v-model="draft.recovery_key" :label="t('fields.recoveryKey')" type="password" />
            </template>
            <FormField v-model="allowedRooms" :label="t('fields.allowedRooms')" textarea wide />
            <details class="advanced-disclosure form-field--wide" open>
              <summary>{{ t("fields.matrixBehavior") }}</summary>
              <div class="form-grid nested-form">
                <label class="check-row form-field--wide"><input v-model="draft.mention_only" type="checkbox" /><span>{{ t("fields.mentionOnly") }}</span></label>
                <label class="check-row form-field--wide"><input v-model="draft.reply_in_thread" type="checkbox" /><span>{{ t("fields.replyInThread") }}</span></label>
                <label class="check-row form-field--wide"><input v-model="draft.ack_reactions" type="checkbox" /><span>{{ t("fields.ackReactions") }}</span></label>
                <label class="check-row form-field--wide"><input v-model="draft.interrupt_on_new_message" type="checkbox" /><span>{{ t("fields.interruptOnNewMessage") }}</span></label>
                <FormField v-model="draft.stream_mode" :label="t('fields.streamMode')" :options="streamOptions" />
                <FormField v-model="draft.multi_message_delay_ms" :label="t('fields.multiMessageDelayMs')" type="number" min="0" :error="formErrors.multi_message_delay_ms" />
                <FormField v-model="draft.channel_debounce_ms" :label="t('fields.channelDebounceMs')" type="number" min="0" :error="formErrors.channel_debounce_ms" />
              </div>
            </details>
            <details class="advanced-disclosure form-field--wide">
              <summary>{{ t("profiles.matrixAdvanced") }}</summary>
              <div class="form-grid nested-form">
                <FormField v-model="draft.draft_update_interval_ms" :label="t('fields.draftUpdateIntervalMs')" type="number" min="0" :error="formErrors.draft_update_interval_ms" />
                <FormField v-model="draft.approval_timeout_secs" :label="t('fields.approvalTimeoutSecs')" type="number" min="1" :error="formErrors.approval_timeout_secs" />
                <FormField v-model="excludedTools" :label="t('fields.excludedTools')" textarea wide />
                <FormField v-model="draft.reply_min_interval_secs" :label="t('fields.replyMinIntervalSecs')" type="number" min="0" :error="formErrors.reply_min_interval_secs" />
                <FormField v-model="draft.reply_queue_depth_max" :label="t('fields.replyQueueDepthMax')" type="number" min="0" :error="formErrors.reply_queue_depth_max" />
                <FormField v-model="draft.host_ip" :label="t('fields.hostIp')" />
              </div>
            </details>
          </template>
          <template v-else>
            <FormField v-model="draft.url" :label="t('fields.url')" :error="formErrors.url" />
            <FormField v-model="draft.command" :label="t('fields.command')" />
          </template>
          <div class="form-field form-field--wide">
            <span>{{ t("profiles.advancedJson") }}</span>
            <small>{{ t("profiles.advancedJsonHelp") }}</small>
            <JsonEditor v-model="draft" @error="advancedJsonError = $event" />
            <small v-if="formErrors.advanced_json" class="field-error">{{ formErrors.advanced_json }}</small>
          </div>
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("actions.save") }}</UiButton>
            <UiButton v-if="kind === 'llm'" type="button" :loading="testingProfile" @click="testProfile"><PlugZap />{{ t("actions.testConnection") }}</UiButton>
            <UiButton v-if="!draft._draft" variant="danger" @click="remove"><Trash2 />{{ t("actions.delete") }}</UiButton>
          </div>
          <p v-if="formMessage" class="field-error form-field--wide">{{ formMessage }}</p>
        </form>
        <p v-else class="empty-text">{{ t("profiles.empty") }}</p>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { PlugZap, Plus, Save, Trash2 } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import JsonEditor from "../components/JsonEditor.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { useToast } from "../composables/useToast.js";
import { clone, itemId } from "../lib/api.js";
import {
  firstError,
  validateHttpUrl,
  validateId,
  validateIntegerRange,
  validateRequired,
  validateSkillBundleId,
  valueExists
} from "../lib/validation.js";
import { issueMessages, mapIssuesToProfileForm, validationIssuesFromError } from "../lib/validationIssues.mjs";
import { useManagerStore } from "../stores/manager.js";

const route = useRoute();
const router = useRouter();
const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const toast = useToast();
const selectedId = ref("");
const draft = ref(null);
const testingProfile = ref(false);
const formErrors = ref({});
const formMessage = ref("");
const advancedJsonError = ref("");
const PROFILE_SELECTION_STORAGE_PREFIX = "zeroclaw.webui.selected.profile.";
const wireOptions = [
  { label: t("profiles.wire.chatCompletions"), value: "chat_completions" },
  { label: t("profiles.wire.responses"), value: "responses" }
];
const streamOptions = [
  { label: t("profiles.stream.multiMessage"), value: "multi_message" },
  { label: t("profiles.stream.edit"), value: "edit" },
  { label: t("common.disabled"), value: "disabled" }
];
const matrixLoginModeOptions = [
  { label: t("matrix.login.account"), value: "account" },
  { label: t("matrix.login.token"), value: "token" },
  { label: t("matrix.login.advanced"), value: "advanced" }
];

const kind = computed(() => route.params.kind || "llm");
const profiles = computed(() => store.profiles[kind.value] || []);
const title = computed(() => t(`${kind.value}.title`));
const description = computed(() => {
  if (kind.value === "matrix") return t("matrix.subtitle");
  if (kind.value === "vision") return t("vision.subtitle");
  if (kind.value === "mcp") return t("mcp.subtitle");
  return t("llm.subtitle");
});

watch(kind, () => {
  selectedId.value = "";
  draft.value = null;
  testingProfile.value = false;
});

watch(
  profiles,
  (items) => {
    const routeId = queryString(route.query.id);
    const storedId = localStorage.getItem(profileSelectionStorageKey()) || "";
    const targetId = routeId || storedId;
    if (targetId && items.some((profile) => itemId(profile) === targetId) && selectedId.value !== targetId) {
      selectProfile(items.find((profile) => itemId(profile) === targetId), { syncRoute: !routeId });
      return;
    }
    if (!draft.value && items.length) selectProfile(items[0]);
  },
  { immediate: true }
);

watch(
  () => route.query.id,
  (profileId) => {
    const profile = profiles.value.find((item) => itemId(item) === queryString(profileId));
    if (profile) selectProfile(profile, { syncRoute: false });
  }
);

function selectProfile(profile, options = {}) {
  selectedId.value = itemId(profile);
  draft.value = clone(profile);
  localStorage.setItem(profileSelectionStorageKey(), selectedId.value);
  if (options.syncRoute !== false) replaceQueryValue("id", selectedId.value);
  testingProfile.value = false;
  formErrors.value = {};
  formMessage.value = "";
  advancedJsonError.value = "";
}

function createProfile() {
  draft.value = { ...store.newProfile(kind.value), _draft: true };
  selectedId.value = "";
  replaceQueryValue("id", "");
  testingProfile.value = false;
  formErrors.value = {};
  formMessage.value = "";
  advancedJsonError.value = "";
}

async function save() {
  if (!validateProfileForm()) return;
  const payload = clone(draft.value);
  delete payload._draft;
  if (kind.value === "matrix") normalizeMatrixLoginPayload(payload);
  try {
    await store.saveProfile(kind.value, payload);
    selectedId.value = itemId(payload);
    draft.value = payload;
    localStorage.setItem(profileSelectionStorageKey(), selectedId.value);
    replaceQueryValue("id", selectedId.value);
    formErrors.value = {};
    formMessage.value = "";
  } catch (error) {
    applyBackendValidation(error, itemId(payload));
  }
}

function applyBackendValidation(error, profileId) {
  const issues = validationIssuesFromError(error);
  if (!issues.length) {
    formMessage.value = error.message || String(error);
    return;
  }
  const mapped = mapIssuesToProfileForm(issues, kind.value, profileId, store.profiles);
  formErrors.value = { ...formErrors.value, ...mapped.errors };
  const messages = issueMessages(mapped.global);
  formMessage.value = messages.length ? messages.join(" ") : t("validation.fixFields");
}

function validateProfileForm() {
  const errors = {};
  const label = (key) => t(`fields.${key}`);
  validateId(errors, "id", draft.value?.id, t("validation.invalidId", { field: label("id") }));
  if (valueExists(profiles.value, draft.value?.id, selectedId.value)) {
    errors.id = t("validation.duplicateValue", { field: label("id") });
  }

  if (kind.value === "llm" || kind.value === "vision") {
    validateSkillBundleId(errors, "provider_family", draft.value?.provider_family, t("validation.invalidSkillBundleId", { field: label("provider") }));
    validateSkillBundleId(errors, "provider_alias", draft.value?.provider_alias, t("validation.invalidSkillBundleId", { field: label("providerAlias") }));
    validateRequired(errors, "model", draft.value?.model, t("messages.requiredField", { field: label("model") }));
    validateHttpUrl(errors, "base_url", draft.value?.base_url, t("messages.invalidUrlField", { field: label("baseUrl") }));
    validateIntegerRange(errors, "timeout_secs", draft.value?.timeout_secs, {
      min: 1,
      message: t("messages.invalidMinNumberField", { field: label("timeout"), min: 1 })
    });
  }

  if (kind.value === "vision") {
    validateIntegerRange(errors, "max_images", draft.value?.max_images, {
      min: 1,
      max: 16,
      message: t("validation.invalidRange", { field: label("maxImages"), min: 1, max: 16 })
    });
    validateIntegerRange(errors, "max_image_size_mb", draft.value?.max_image_size_mb, {
      min: 1,
      max: 20,
      message: t("validation.invalidRange", { field: label("maxImageSizeMb"), min: 1, max: 20 })
    });
    validateIntegerRange(errors, "max_image_turns", draft.value?.max_image_turns, {
      min: 0,
      message: t("messages.invalidMinNumberField", { field: label("maxImageTurns"), min: 0 })
    });
  }

  if (kind.value === "llm") {
    validateIntegerRange(errors, "temperature", draft.value?.temperature, {
      min: 0,
      max: 2,
      message: t("validation.invalidRange", { field: label("temperature"), min: 0, max: 2 })
    });
    validateIntegerRange(errors, "max_tokens", draft.value?.max_tokens, {
      min: 1,
      message: t("messages.invalidMinNumberField", { field: label("maxTokens"), min: 1 })
    });
  }

  if (kind.value === "matrix") {
    validateRequired(errors, "homeserver", draft.value?.homeserver, t("messages.requiredField", { field: label("homeserver") }));
    validateHttpUrl(errors, "homeserver", draft.value?.homeserver, t("messages.invalidUrlField", { field: label("homeserver") }));
    if (matrixLoginMode.value === "token") {
      validateRequired(errors, "device_id", draft.value?.device_id, t("messages.requiredField", { field: label("deviceId") }));
      validateRequired(errors, "access_token", draft.value?.access_token, t("messages.requiredField", { field: label("accessToken") }));
    } else if (matrixLoginMode.value === "advanced") {
      const hasAccount = Boolean(draft.value?.user_id && draft.value?.password);
      const hasToken = Boolean(draft.value?.device_id && draft.value?.access_token);
      if (!hasAccount && !hasToken) {
        validateRequired(errors, "user_id", draft.value?.user_id, t("messages.requiredField", { field: label("matrixUser") }));
        validateRequired(errors, "password", draft.value?.password, t("messages.requiredField", { field: label("password") }));
        validateRequired(errors, "device_id", draft.value?.device_id, t("messages.requiredField", { field: label("deviceId") }));
        validateRequired(errors, "access_token", draft.value?.access_token, t("messages.requiredField", { field: label("accessToken") }));
      }
    } else {
      validateRequired(errors, "user_id", draft.value?.user_id, t("messages.requiredField", { field: label("matrixUser") }));
      validateRequired(errors, "password", draft.value?.password, t("messages.requiredField", { field: label("password") }));
    }
    for (const key of [
      "multi_message_delay_ms",
      "channel_debounce_ms",
      "draft_update_interval_ms",
      "reply_min_interval_secs",
      "reply_queue_depth_max"
    ]) {
      validateIntegerRange(errors, key, draft.value?.[key], {
        min: 0,
        message: t("messages.invalidMinNumberField", { field: t(`fields.${camelField(key)}`), min: 0 })
      });
    }
    validateIntegerRange(errors, "approval_timeout_secs", draft.value?.approval_timeout_secs, {
      min: 1,
      message: t("messages.invalidMinNumberField", { field: label("approvalTimeoutSecs"), min: 1 })
    });
  }

  if (kind.value === "mcp") {
    validateHttpUrl(errors, "url", draft.value?.url, t("messages.invalidUrlField", { field: label("url") }));
  }

  if (advancedJsonError.value) {
    errors.advanced_json = t("validation.invalidJson", { field: t("profiles.advancedJson") });
  }
  formErrors.value = errors;
  formMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  return !formMessage.value;
}

function camelField(key) {
  return key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

async function remove() {
  if (!draft.value?._draft && await dialog.confirm(t("confirm.deleteProfileNamed", { kind: t(`${kind.value}.title`), id: itemId(draft.value) }))) {
    await store.deleteProfile(kind.value, itemId(draft.value));
    localStorage.removeItem(profileSelectionStorageKey());
    replaceQueryValue("id", "");
    draft.value = null;
    selectedId.value = "";
  }
}

function lines(value) {
  return String(value || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function parseJsonField(value, fallback) {
  try {
    return JSON.parse(value || "null") ?? fallback;
  } catch (_error) {
    return fallback;
  }
}

function jsonComputed(key, fallback) {
  return computed({
    get: () => JSON.stringify(draft.value?.[key] ?? fallback, null, 2),
    set: (value) => (draft.value[key] = parseJsonField(value, fallback))
  });
}

const fallbackModels = computed({
  get: () => (draft.value?.fallback_models || draft.value?.fallback || []).join("\n"),
  set: (value) => (draft.value.fallback_models = lines(value))
});
const extraHeaders = jsonComputed("extra_headers", {});
const providerExtra = jsonComputed("provider_extra", {});
const pricing = jsonComputed("pricing", {});
const allowedRooms = computed({
  get: () => (draft.value?.allowed_rooms || []).join("\n"),
  set: (value) => (draft.value.allowed_rooms = lines(value))
});
const excludedTools = computed({
  get: () => (draft.value?.excluded_tools || []).join("\n"),
  set: (value) => (draft.value.excluded_tools = lines(value))
});
const matrixLoginMode = computed({
  get: () => draft.value?.login_mode || inferMatrixLoginMode(draft.value),
  set: (value) => {
    if (!draft.value) return;
    draft.value.login_mode = ["account", "token", "advanced"].includes(value) ? value : "account";
    normalizeMatrixLoginPayload(draft.value);
  }
});

function inferMatrixLoginMode(profile) {
  if (profile?.login_mode === "advanced") return "advanced";
  return profile?.access_token || profile?.login_mode === "token" ? "token" : "account";
}

function normalizeMatrixLoginPayload(profile) {
  const mode = ["account", "token", "advanced"].includes(profile.login_mode) ? profile.login_mode : "account";
  profile.login_mode = mode;
  if (mode === "advanced") return;
  if (mode === "token") {
    delete profile.password;
    delete profile.recovery_key;
  } else {
    delete profile.access_token;
    delete profile.device_id;
  }
}

async function testProfile() {
  const payload = clone(draft.value);
  delete payload._draft;
  testingProfile.value = true;
  try {
    const result = await store.testLlmProfile(payload);
    const latency = result.latency_ms ?? 0;
    const model = result.model || payload.model || "";
    const preview = result.preview ? ` ${result.preview}` : "";
    toast.success(`${t("profiles.testPassed")} ${model} / ${latency}ms.${preview}`);
  } catch (error) {
    store.setError(error);
  } finally {
    testingProfile.value = false;
  }
}

function profileSelectionStorageKey() {
  return `${PROFILE_SELECTION_STORAGE_PREFIX}${kind.value}`;
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

function profileUsage(profileId) {
  const field = `${kind.value}_profile`;
  return store.agents
    .filter((agent) => agent[field] === profileId)
    .map((agent) => ({ id: itemId(agent), field }));
}

const currentUsage = computed(() => (draft.value ? profileUsage(itemId(draft.value)) : []));
</script>
