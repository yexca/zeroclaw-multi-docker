<template>
  <section class="view-stack">
    <PageHeader :title="title" :description="description">
      <UiButton variant="primary" @click="createProfile"><Plus />New profile</UiButton>
    </PageHeader>

    <div class="editor-layout">
      <UiCard title="Profiles" description="Reusable settings assigned by agents.">
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
              <small>{{ profile.model || profile.homeserver || profile.url || profile.provider_family || "Profile" }}</small>
            </span>
            <mark :class="profileUsage(itemId(profile)).length ? 'good' : ''">
              {{ profileUsage(itemId(profile)).length ? `used ${profileUsage(itemId(profile)).length}` : "unused" }}
            </mark>
          </button>
          <p v-if="!profiles.length" class="empty-text">No profiles yet.</p>
        </div>
      </UiCard>

      <UiCard title="Profile details" description="Edit common fields directly; use JSON for advanced settings.">
        <section v-if="draft" class="profile-usage-panel">
          <div>
            <strong>Used by</strong>
            <span>{{ currentUsage.length ? `${currentUsage.length} agent${currentUsage.length === 1 ? "" : "s"}` : "No agents use this profile." }}</span>
          </div>
          <div v-if="currentUsage.length" class="file-chip-grid">
            <button v-for="usage in currentUsage" :key="`${usage.id}-${usage.field}`" class="file-chip profile-usage-chip" type="button">
              {{ usage.id }} · {{ usage.field }}
            </button>
          </div>
        </section>
        <form v-if="draft" class="form-grid" @submit.prevent="save">
          <FormField v-model="draft.id" label="ID" />
          <template v-if="kind === 'llm' || kind === 'vision'">
            <FormField v-model="draft.provider_family" label="Provider family" />
            <FormField v-model="draft.provider_alias" label="Provider alias" />
            <FormField v-model="draft.model" label="Model" />
            <FormField v-model="draft.base_url" label="Base URL" />
            <FormField v-model="draft.api_key" label="API key" type="password" />
            <FormField v-model="draft.wire_api" label="Wire API" :options="wireOptions" />
            <FormField v-model="draft.timeout_secs" label="Timeout seconds" type="number" />
            <template v-if="kind === 'vision'">
              <details class="advanced-disclosure form-field--wide">
                <summary>Multimodal limits</summary>
                <div class="form-grid nested-form">
                  <FormField v-model="draft.max_images" label="Max images" type="number" />
                  <FormField v-model="draft.max_image_size_mb" label="Max image size MB" type="number" />
                  <FormField v-model="draft.max_image_turns" label="Max image turns" type="number" />
                  <label class="check-row form-field--wide">
                    <input v-model="draft.allow_remote_fetch" type="checkbox" />
                    <span>Allow remote image fetch</span>
                  </label>
                </div>
              </details>
            </template>
            <template v-else>
              <details class="advanced-disclosure form-field--wide">
                <summary>LLM advanced</summary>
                <div class="form-grid nested-form">
                  <FormField v-model="draft.temperature" label="Temperature" type="number" />
                  <FormField v-model="draft.max_tokens" label="Max tokens" type="number" />
                  <FormField v-model="fallbackModels" label="Fallback models" textarea wide />
                  <FormField v-model="extraHeaders" label="Extra headers JSON" textarea wide />
                  <FormField v-model="providerExtra" label="Provider extra JSON" textarea wide />
                  <FormField v-model="pricing" label="Pricing JSON" textarea wide />
                  <label class="check-row form-field--wide">
                    <input v-model="draft.requires_openai_auth" type="checkbox" />
                    <span>Requires OpenAI auth</span>
                  </label>
                  <label class="check-row form-field--wide">
                    <input v-model="draft.merge_system_into_user" type="checkbox" />
                    <span>Merge system into user</span>
                  </label>
                </div>
              </details>
            </template>
          </template>
          <template v-else-if="kind === 'matrix'">
            <FormField v-model="draft.homeserver" label="Homeserver" />
            <FormField v-model="draft.user_id" label="Matrix user" />
            <FormField v-model="draft.device_id" label="Device ID" />
            <FormField v-model="draft.password" label="Password" type="password" />
            <FormField v-model="draft.recovery_key" label="Recovery key" type="password" />
            <FormField v-model="allowedRooms" label="Allowed rooms" textarea wide />
            <details class="advanced-disclosure form-field--wide" open>
              <summary>Matrix behavior</summary>
              <div class="form-grid nested-form">
                <label class="check-row form-field--wide"><input v-model="draft.mention_only" type="checkbox" /><span>Mention only</span></label>
                <label class="check-row form-field--wide"><input v-model="draft.reply_in_thread" type="checkbox" /><span>Reply in thread</span></label>
                <label class="check-row form-field--wide"><input v-model="draft.ack_reactions" type="checkbox" /><span>Ack reactions</span></label>
                <label class="check-row form-field--wide"><input v-model="draft.interrupt_on_new_message" type="checkbox" /><span>Interrupt on new message</span></label>
                <FormField v-model="draft.stream_mode" label="Stream mode" :options="streamOptions" />
                <FormField v-model="draft.multi_message_delay_ms" label="Multi-message delay ms" type="number" />
                <FormField v-model="draft.channel_debounce_ms" label="Channel debounce ms" type="number" />
                <FormField v-model="draft.access_token" label="Access token" type="password" wide />
              </div>
            </details>
            <details class="advanced-disclosure form-field--wide">
              <summary>Matrix advanced</summary>
              <div class="form-grid nested-form">
                <FormField v-model="draft.draft_update_interval_ms" label="Draft update interval ms" type="number" />
                <FormField v-model="draft.approval_timeout_secs" label="Approval timeout secs" type="number" />
                <FormField v-model="excludedTools" label="Excluded tools" textarea wide />
                <FormField v-model="draft.reply_min_interval_secs" label="Reply min interval secs" type="number" />
                <FormField v-model="draft.reply_queue_depth_max" label="Reply queue depth max" type="number" />
                <FormField v-model="draft.host_ip" label="Host IP override" />
              </div>
            </details>
          </template>
          <template v-else>
            <FormField v-model="draft.url" label="URL" />
            <FormField v-model="draft.command" label="Command" />
          </template>
          <div class="form-field form-field--wide">
            <span>Advanced JSON</span>
            <small>Full object editor. Leave secret fields unchanged unless you intend to replace them.</small>
            <JsonEditor v-model="draft" />
          </div>
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />Save</UiButton>
            <UiButton v-if="kind === 'llm'" type="button" @click="testProfile"><PlugZap />Test</UiButton>
            <UiButton v-if="!draft._draft" variant="danger" @click="remove"><Trash2 />Delete</UiButton>
          </div>
        </form>
        <p v-else class="empty-text">Select or create a profile.</p>
      </UiCard>
    </div>

    <div v-if="testResult" class="split-panels">
      <UiCard v-if="testResult" title="LLM test result">
        <pre class="code-block">{{ JSON.stringify(testResult, null, 2) }}</pre>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { PlugZap, Plus, Save, Trash2 } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import JsonEditor from "../components/JsonEditor.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { clone, itemId } from "../lib/api.js";
import { useManagerStore } from "../stores/manager.js";

const route = useRoute();
const store = useManagerStore();
const selectedId = ref("");
const draft = ref(null);
const testResult = ref(null);
const wireOptions = [
  { label: "Chat Completions", value: "chat_completions" },
  { label: "Responses", value: "responses" }
];
const streamOptions = [
  { label: "Multi message", value: "multi_message" },
  { label: "Edit", value: "edit" },
  { label: "Disabled", value: "disabled" }
];

const kind = computed(() => route.params.kind || "llm");
const profiles = computed(() => store.profiles[kind.value] || []);
const title = computed(() => `${kind.value.toUpperCase()} Profiles`);
const description = computed(() => {
  if (kind.value === "matrix") return "Homeserver identity, rooms, and channel behavior.";
  if (kind.value === "vision") return "Vision-capable model routes for image turns.";
  if (kind.value === "mcp") return "Gateway and server profiles for tools.";
  return "Model provider profiles used by agents.";
});

watch(kind, () => {
  selectedId.value = "";
  draft.value = null;
  testResult.value = null;
});

watch(
  profiles,
  (items) => {
    if (!draft.value && items.length) selectProfile(items[0]);
  },
  { immediate: true }
);

function selectProfile(profile) {
  selectedId.value = itemId(profile);
  draft.value = clone(profile);
  testResult.value = null;
}

function createProfile() {
  draft.value = { ...store.newProfile(kind.value), _draft: true };
  selectedId.value = "";
  testResult.value = null;
}

async function save() {
  const payload = clone(draft.value);
  delete payload._draft;
  await store.saveProfile(kind.value, payload);
  selectedId.value = itemId(payload);
  draft.value = payload;
}

async function remove() {
  if (!draft.value?._draft && confirm(`Delete ${kind.value} profile ${itemId(draft.value)}?`)) {
    await store.deleteProfile(kind.value, itemId(draft.value));
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

async function testProfile() {
  const payload = clone(draft.value);
  delete payload._draft;
  testResult.value = await store.testLlmProfile(payload);
}

function profileUsage(profileId) {
  const field = `${kind.value}_profile`;
  return store.agents
    .filter((agent) => agent[field] === profileId)
    .map((agent) => ({ id: itemId(agent), field }));
}

const currentUsage = computed(() => (draft.value ? profileUsage(itemId(draft.value)) : []));
</script>
