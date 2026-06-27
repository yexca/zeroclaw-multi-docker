<template>
  <section class="view-stack">
    <PageHeader title="Agents" description="Create agents, wire reusable profiles, and control runtime containers.">
      <UiButton variant="primary" @click="createAgent"><Plus />New agent</UiButton>
    </PageHeader>

    <div class="editor-layout">
      <UiCard title="Agent list" description="Drafts become runnable after their prompt template is applied.">
        <div class="item-list">
          <button v-for="agent in store.agents" :key="itemId(agent)" :class="{ active: selectedId === itemId(agent) }" @click="selectAgent(agent)">
            <strong>{{ itemId(agent) }}</strong>
            <span>{{ agent.llm_profile || "No LLM" }} / {{ agent.matrix_profile || "No Matrix" }}</span>
          </button>
          <p v-if="!store.agents.length" class="empty-text">No agents yet.</p>
        </div>
      </UiCard>

      <UiCard title="Agent details" :description="draft?._draft ? 'New unsaved agent.' : 'Core runtime and profile wiring.'">
        <form v-if="draft" class="form-grid" @submit.prevent="save">
          <FormField v-model="draft.id" label="Agent ID" />
          <FormField v-model="draft.host_port" label="Host port" type="number" />
          <FormField v-model="draft.llm_profile" label="LLM profile" :options="profileOptions('llm')" />
          <FormField v-model="draft.vision_profile" label="Vision profile" :options="profileOptions('vision', true)" />
          <FormField v-model="draft.matrix_profile" label="Matrix profile" :options="profileOptions('matrix')" />
          <FormField v-model="draft.mcp_profile" label="MCP profile" :options="profileOptions('mcp', true)" />
          <FormField v-model="draft.prompt_template" label="Prompt template" :options="templateOptions" />
          <FormField v-model="draft.image" label="Docker image" wide />
          <FormField v-model="externalPeers" label="External peers" textarea wide />
          <FormField v-model="skillBundles" label="Skill bundles" textarea wide />
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />Save</UiButton>
            <UiButton v-if="!draft._draft" @click="store.controlAgent(draft.id, 'start')"><Play />Start</UiButton>
            <UiButton v-if="!draft._draft" @click="store.controlAgent(draft.id, 'restart')"><RotateCw />Restart</UiButton>
            <UiButton v-if="!draft._draft" variant="danger" @click="remove"><Trash2 />Delete</UiButton>
          </div>
        </form>
        <p v-else class="empty-text">Select or create an agent.</p>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { Plus, Play, RotateCw, Save, Trash2 } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { clone, itemId } from "../lib/api.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const selectedId = ref("");
const draft = ref(null);

watch(
  () => store.agents,
  (agents) => {
    if (!draft.value && agents.length) selectAgent(agents[0]);
  },
  { immediate: true }
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

const templateOptions = computed(() => [
  { label: "None", value: "" },
  ...store.templates.map((template) => ({ label: itemId(template), value: itemId(template) }))
]);

function profileOptions(kind, optional = false) {
  const values = (store.profiles[kind] || []).map((profile) => ({ label: itemId(profile), value: itemId(profile) }));
  return optional ? [{ label: "None", value: "" }, ...values] : values;
}

function selectAgent(agent) {
  selectedId.value = itemId(agent);
  draft.value = clone(agent);
}

function createAgent() {
  draft.value = { ...store.newAgent(), _draft: true };
  selectedId.value = "";
}

async function save() {
  const payload = clone(draft.value);
  delete payload._draft;
  await store.saveAgent(payload);
  selectedId.value = payload.id;
  draft.value = payload;
}

async function remove() {
  if (!draft.value?._draft && confirm(`Delete agent ${draft.value.id}?`)) {
    await store.deleteAgent(draft.value.id);
    draft.value = null;
    selectedId.value = "";
  }
}
</script>
