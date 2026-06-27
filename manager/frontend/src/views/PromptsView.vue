<template>
  <section class="view-stack">
    <PageHeader :title="t('prompts.title')" :description="t('prompts.subtitle')">
      <UiButton variant="primary" @click="createTemplate"><Plus />{{ t("prompts.newTemplate") }}</UiButton>
    </PageHeader>

    <div class="editor-layout">
      <UiCard :title="t('prompts.templates')">
        <template #actions>
          <UiButton v-if="draft" @click="duplicateTemplate"><Copy />{{ t("actions.duplicate") }}</UiButton>
        </template>
        <div class="item-list">
          <button v-for="template in store.templates" :key="itemId(template)" :class="{ active: selectedId === itemId(template) }" @click="selectTemplate(template)">
            <strong>{{ itemId(template) }}</strong>
            <span>{{ t("prompts.fileCount", { count: Object.keys(template.files || {}).length }) }}</span>
          </button>
          <p v-if="!store.templates.length" class="empty-text">{{ t("prompts.emptyList") }}</p>
        </div>
      </UiCard>

      <UiCard :title="t('prompts.details')" :description="t('prompts.detailsHelp')">
        <form v-if="draft" class="form-grid" @submit.prevent="save">
          <FormField v-model="draft.id" :label="t('prompts.templateId')" :error="formErrors.id" required />
          <FormField v-model="draft.description" :label="t('fields.description')" wide />
          <div class="form-field form-field--wide">
            <span>{{ t("prompts.filesLabel") }}</span>
            <div class="file-tabs">
              <button v-for="file in fileNames" :key="file" :class="{ active: selectedFile === file }" type="button" @click="selectedFile = file">
                {{ file }}
                <small>{{ fileBadge(file) }}</small>
              </button>
              <button type="button" @click="addFile"><Plus />{{ t("prompts.file") }}</button>
            </div>
            <small v-if="formErrors.files" class="field-error">{{ formErrors.files }}</small>
            <div v-if="selectedFile" class="template-file-meta">
              <strong>{{ selectedFile }}</strong>
              <span>{{ fileHelp(selectedFile) }}</span>
              <div class="button-row">
                <UiButton type="button" @click="renameFile"><Pencil />{{ t("prompts.rename") }}</UiButton>
                <UiButton type="button" variant="danger" :disabled="protectedFile(selectedFile)" @click="deleteFile"><Trash2 />{{ t("actions.delete") }}</UiButton>
              </div>
            </div>
            <textarea v-if="selectedFile" v-model="draft.files[selectedFile]" class="template-editor-text" spellcheck="false" />
          </div>
          <div class="form-field form-field--wide">
            <details class="advanced-disclosure">
              <summary>{{ t("profiles.advancedJson") }}</summary>
              <JsonEditor v-model="draft" />
            </details>
          </div>
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("actions.save") }}</UiButton>
            <UiButton type="button" @click="aiFillOpen = !aiFillOpen"><Sparkles />{{ t("actions.aiFill") }}</UiButton>
            <UiButton v-if="!draft._draft" type="button" variant="danger" @click="deleteTemplate"><Trash2 />{{ t("prompts.deleteTemplate") }}</UiButton>
          </div>
          <p v-if="formMessage" class="field-error form-field--wide">{{ formMessage }}</p>
        </form>
        <p v-else class="empty-text">{{ t("prompts.empty") }}</p>
      </UiCard>
    </div>

    <UiCard v-if="draft && aiFillOpen" :title="t('prompts.aiFillTitle')" :description="t('prompts.aiFillSubtitle')">
      <form class="form-grid" @submit.prevent="runAiFill">
        <FormField v-model="aiFill.llm_profile" :label="t('fields.llmProfile')" :options="llmOptions" />
        <FormField v-model="aiFill.description" :label="t('prompts.aiDescription')" wide />
        <FormField v-model="aiFill.instruction" :label="t('prompts.aiInstruction')" textarea wide />
        <div class="form-field form-field--wide">
          <span>{{ t("prompts.targetFiles") }}</span>
          <div class="file-chip-grid">
            <label v-for="file in fileNames" :key="file" class="check-row file-chip">
              <input v-model="aiFill.files" :value="file" type="checkbox" />
              <span>{{ file }}</span>
            </label>
          </div>
        </div>
        <div class="form-field form-field--wide">
          <span>{{ t("prompts.referenceFiles") }}</span>
          <div class="file-chip-grid">
            <label v-for="file in fileNames" :key="file" class="check-row file-chip">
              <input v-model="aiFill.reference_files" :value="file" type="checkbox" />
              <span>{{ file }}</span>
            </label>
          </div>
        </div>
        <div class="button-row form-field--wide">
          <UiButton variant="primary" type="submit"><Sparkles />{{ t("actions.generate") }}</UiButton>
          <UiButton type="button" @click="aiFillOpen = false">{{ t("actions.close") }}</UiButton>
        </div>
      </form>
    </UiCard>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { Copy, Pencil, Plus, Save, Sparkles, Trash2 } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import JsonEditor from "../components/JsonEditor.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { clone, itemId } from "../lib/api.js";
import { firstError, validateId, validatePromptFileName, valueExists } from "../lib/validation.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const PROMPT_SYSTEM_FILES = ["AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "MEMORY.md"];
const TEMPLATE_FILES = [...PROMPT_SYSTEM_FILES, "HEARTBEAT.md", "PROACTIVE.md"];
const selectedId = ref("");
const draft = ref(null);
const selectedFile = ref("");
const formErrors = ref({});
const formMessage = ref("");
const aiFillOpen = ref(false);
const aiFill = ref({
  llm_profile: "",
  instruction: t("prompts.defaultAiInstruction"),
  description: "",
  files: [],
  reference_files: []
});

const fileNames = computed(() => Object.keys(draft.value?.files || {}));
const llmOptions = computed(() => store.profiles.llm.map((profile) => ({ label: itemId(profile), value: itemId(profile) })));

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
  formErrors.value = {};
  formMessage.value = "";
  resetAiFill();
}

function createTemplate() {
  const next = store.templates.length + 1;
  draft.value = { id: `template-${next}`, description: "", files: { "AGENTS.md": "" }, _draft: true };
  selectedId.value = "";
  selectedFile.value = "AGENTS.md";
  formErrors.value = {};
  formMessage.value = "";
  resetAiFill();
}

function duplicateTemplate() {
  if (!draft.value) return;
  const copy = clone(draft.value);
  copy.id = nextTemplateId(`${itemId(copy)}-copy`);
  copy._draft = true;
  selectedId.value = "";
  draft.value = copy;
  selectedFile.value = Object.keys(copy.files || {})[0] || "";
  resetAiFill();
}

async function save() {
  if (!validateTemplateForm()) return;
  const payload = clone(draft.value);
  payload.files = payload.files || {};
  delete payload._draft;
  await store.saveTemplate(payload);
  selectedId.value = payload.id;
  draft.value = payload;
  formErrors.value = {};
  formMessage.value = "";
}

async function deleteTemplate() {
  if (!draft.value || !(await dialog.confirm(t("confirm.deleteTemplateNamed", { id: itemId(draft.value) })))) return;
  await store.deleteTemplate(itemId(draft.value));
  draft.value = null;
  selectedId.value = "";
  selectedFile.value = "";
}

async function addFile() {
  const name = await dialog.prompt(t("prompts.addFilePrompt"), "USER.md");
  if (!name) return;
  const normalized = validateFilename(name);
  if (!normalized) return;
  if (!draft.value.files) draft.value.files = {};
  if (!(normalized in draft.value.files)) draft.value.files[normalized] = "";
  selectedFile.value = normalized;
  if (!aiFill.value.files.includes(normalized)) aiFill.value.files.push(normalized);
}

async function renameFile() {
  if (!selectedFile.value) return;
  const next = await dialog.prompt(t("prompts.renameFilePrompt"), selectedFile.value);
  if (!next) return;
  const normalized = validateFilename(next);
  if (!normalized) return;
  if (normalized === selectedFile.value) return;
  if (draft.value.files?.[normalized] !== undefined) {
    formErrors.value = { ...formErrors.value, files: t("prompts.fileExists") };
    formMessage.value = t("validation.fixFields");
    return;
  }
  draft.value.files[normalized] = draft.value.files[selectedFile.value] || "";
  delete draft.value.files[selectedFile.value];
  selectedFile.value = normalized;
  formErrors.value = { ...formErrors.value, files: "" };
  formMessage.value = firstError(formErrors.value) ? t("validation.fixFields") : "";
  resetAiFill();
}

async function deleteFile() {
  if (!selectedFile.value || protectedFile(selectedFile.value)) return;
  if (!(await dialog.confirm(t("confirm.deleteTemplateFileNamed", { file: selectedFile.value })))) return;
  delete draft.value.files[selectedFile.value];
  selectedFile.value = Object.keys(draft.value.files || {})[0] || "";
  resetAiFill();
}

function resetAiFill() {
  const files = Object.keys(draft.value?.files || {});
  aiFill.value = {
    llm_profile: store.profiles.llm[0] ? itemId(store.profiles.llm[0]) : "",
    instruction: aiFill.value.instruction,
    description: draft.value?.description || "",
    files: files.slice(0, Math.min(files.length, 3)),
    reference_files: []
  };
}

async function runAiFill() {
  const currentFiles = Object.fromEntries(
    [...new Set([...aiFill.value.files, ...aiFill.value.reference_files])].map((file) => [file, draft.value.files?.[file] || ""])
  );
  const result = await store.aiFillTemplate({
    llm_profile: aiFill.value.llm_profile,
    instruction: aiFill.value.instruction,
    description: aiFill.value.description,
    files: aiFill.value.files,
    reference_files: aiFill.value.reference_files,
    current_files: currentFiles
  });
  for (const [file, content] of Object.entries(result.files || {})) {
    draft.value.files[file] = content;
    selectedFile.value = file;
  }
}

function protectedFile(file) {
  return TEMPLATE_FILES.includes(file);
}

function fileBadge(file) {
  const index = PROMPT_SYSTEM_FILES.indexOf(file);
  if (index >= 0) return t("prompts.readOrder", { n: index + 1 });
  if (file === "HEARTBEAT.md") return t("prompts.heartbeatOnly");
  if (file === "PROACTIVE.md") return t("prompts.optionalServiceFile");
  return t("prompts.customFile");
}

function fileHelp(file) {
  if (PROMPT_SYSTEM_FILES.includes(file)) return t("prompts.officialFileHelp");
  if (file === "HEARTBEAT.md") return t("prompts.heartbeatFileHelp");
  if (file === "PROACTIVE.md") return t("prompts.optionalServiceFileHelp");
  return t("prompts.customFileHelp");
}

function validateFilename(value) {
  const errors = {};
  const filename = validatePromptFileName(errors, "files", value, t("prompts.invalidFileName"));
  if (errors.files) {
    formErrors.value = { ...formErrors.value, files: errors.files };
    formMessage.value = t("validation.fixFields");
    return "";
  }
  formErrors.value = { ...formErrors.value, files: "" };
  formMessage.value = firstError(formErrors.value) ? t("validation.fixFields") : "";
  return filename;
}

function validateTemplateForm() {
  const errors = {};
  validateId(errors, "id", draft.value?.id, t("validation.invalidId", { field: t("prompts.templateId") }));
  if (valueExists(store.templates, draft.value?.id, selectedId.value)) {
    errors.id = t("validation.duplicateValue", { field: t("prompts.templateId") });
  }
  for (const file of Object.keys(draft.value?.files || {})) {
    validatePromptFileName(errors, "files", file, t("prompts.invalidFileName"));
    if (errors.files) break;
  }
  formErrors.value = errors;
  formMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  return !formMessage.value;
}

function nextTemplateId(prefix) {
  const taken = new Set(store.templates.map((template) => itemId(template)));
  let base = String(prefix || "template").replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "") || "template";
  let candidate = base;
  let index = 2;
  while (taken.has(candidate)) candidate = `${base}-${index++}`;
  return candidate;
}
</script>
