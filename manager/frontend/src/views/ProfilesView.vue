<template>
  <section class="view-stack">
    <PageHeader :title="title" :description="description">
      <UiButton variant="primary" @click="createProfile"><Plus />New profile</UiButton>
    </PageHeader>

    <div class="editor-layout">
      <UiCard title="Profiles" description="Reusable settings assigned by agents.">
        <div class="item-list">
          <button v-for="profile in profiles" :key="itemId(profile)" :class="{ active: selectedId === itemId(profile) }" @click="selectProfile(profile)">
            <strong>{{ itemId(profile) }}</strong>
            <span>{{ profile.model || profile.homeserver || profile.url || profile.provider_family || "Profile" }}</span>
          </button>
          <p v-if="!profiles.length" class="empty-text">No profiles yet.</p>
        </div>
      </UiCard>

      <UiCard title="Profile details" description="Edit common fields directly; use JSON for advanced settings.">
        <form v-if="draft" class="form-grid" @submit.prevent="save">
          <FormField v-model="draft.id" label="ID" />
          <template v-if="kind === 'llm' || kind === 'vision'">
            <FormField v-model="draft.provider_family" label="Provider family" />
            <FormField v-model="draft.provider_alias" label="Provider alias" />
            <FormField v-model="draft.model" label="Model" />
            <FormField v-model="draft.base_url" label="Base URL" />
            <FormField v-model="draft.wire_api" label="Wire API" :options="wireOptions" />
            <FormField v-model="draft.timeout_secs" label="Timeout seconds" type="number" />
          </template>
          <template v-else-if="kind === 'matrix'">
            <FormField v-model="draft.homeserver" label="Homeserver" />
            <FormField v-model="draft.user_id" label="Matrix user" />
            <FormField v-model="draft.device_id" label="Device ID" />
            <FormField v-model="draft.password" label="Password" type="password" />
            <FormField v-model="draft.recovery_key" label="Recovery key" type="password" />
          </template>
          <template v-else>
            <FormField v-model="draft.url" label="URL" />
            <FormField v-model="draft.command" label="Command" />
          </template>
          <div class="form-field form-field--wide">
            <span>Advanced JSON</span>
            <JsonEditor v-model="draft" />
          </div>
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />Save</UiButton>
            <UiButton v-if="!draft._draft" variant="danger" @click="remove"><Trash2 />Delete</UiButton>
          </div>
        </form>
        <p v-else class="empty-text">Select or create a profile.</p>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { Plus, Save, Trash2 } from "@lucide/vue";
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
const wireOptions = [
  { label: "Chat Completions", value: "chat_completions" },
  { label: "Responses", value: "responses" }
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
}

function createProfile() {
  draft.value = { ...store.newProfile(kind.value), _draft: true };
  selectedId.value = "";
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
</script>
