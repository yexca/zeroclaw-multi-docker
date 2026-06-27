<template>
  <section class="view-stack">
    <PageHeader title="Prompt Templates" description="Edit reusable workspace prompt files as structured templates.">
      <UiButton variant="primary" @click="createTemplate"><Plus />New template</UiButton>
    </PageHeader>

    <div class="editor-layout">
      <UiCard title="Templates">
        <div class="item-list">
          <button v-for="template in store.templates" :key="itemId(template)" :class="{ active: selectedId === itemId(template) }" @click="selectTemplate(template)">
            <strong>{{ itemId(template) }}</strong>
            <span>{{ Object.keys(template.files || {}).length }} files</span>
          </button>
          <p v-if="!store.templates.length" class="empty-text">No templates yet.</p>
        </div>
      </UiCard>

      <UiCard title="Template details" description="Use JSON to preserve arbitrary prompt file mappings.">
        <form v-if="draft" class="form-grid" @submit.prevent="save">
          <FormField v-model="draft.id" label="Template ID" />
          <FormField v-model="draft.description" label="Description" wide />
          <div class="form-field form-field--wide">
            <span>Files</span>
            <div class="file-tabs">
              <button v-for="file in fileNames" :key="file" :class="{ active: selectedFile === file }" type="button" @click="selectedFile = file">
                {{ file }}
              </button>
              <button type="button" @click="addFile"><Plus />File</button>
            </div>
            <textarea v-if="selectedFile" v-model="draft.files[selectedFile]" class="template-editor-text" spellcheck="false" />
          </div>
          <div class="form-field form-field--wide">
            <details class="advanced-disclosure">
              <summary>Advanced JSON</summary>
              <JsonEditor v-model="draft" />
            </details>
          </div>
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />Save</UiButton>
          </div>
        </form>
        <p v-else class="empty-text">Select or create a template.</p>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { Plus, Save } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import JsonEditor from "../components/JsonEditor.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { clone, itemId } from "../lib/api.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const selectedId = ref("");
const draft = ref(null);
const selectedFile = ref("");

const fileNames = computed(() => Object.keys(draft.value?.files || {}));

watch(
  () => store.templates,
  (templates) => {
    if (!draft.value && templates.length) selectTemplate(templates[0]);
  },
  { immediate: true }
);

function selectTemplate(template) {
  selectedId.value = itemId(template);
  draft.value = clone(template);
  selectedFile.value = Object.keys(draft.value.files || {})[0] || "";
}

function createTemplate() {
  const next = store.templates.length + 1;
  draft.value = { id: `template-${next}`, description: "", files: { "AGENTS.md": "" }, _draft: true };
  selectedId.value = "";
  selectedFile.value = "AGENTS.md";
}

async function save() {
  const payload = clone(draft.value);
  payload.files = payload.files || {};
  delete payload._draft;
  await store.saveTemplate(payload);
  selectedId.value = payload.id;
  draft.value = payload;
}

function addFile() {
  const name = prompt("File name", "USER.md");
  if (!name) return;
  if (!draft.value.files) draft.value.files = {};
  if (!(name in draft.value.files)) draft.value.files[name] = "";
  selectedFile.value = name;
}
</script>
