<template>
  <section class="view-stack">
    <PageHeader :title="t('prompts.title')" :description="t('prompts.subtitle')">
      <UiButton variant="primary" @click="createTemplate"><Plus />{{ t("prompts.newTemplate") }}</UiButton>
    </PageHeader>

    <div class="editor-layout prompts-layout">
      <UiCard class="sticky-panel prompts-template-list-panel" :title="t('prompts.templates')">
        <template #actions>
          <UiButton v-if="draft" icon :tooltip="t('actions.duplicate')" aria-label="Duplicate template" @click="duplicateTemplate"><Copy /></UiButton>
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
        <form v-if="draft" class="prompt-template-form" @submit.prevent="save">
          <div class="prompt-template-meta">
            <FormField v-model="draft.id" :label="t('prompts.templateId')" :error="formErrors.id" required />
            <FormField v-model="draft.description" :label="t('fields.description')" />
          </div>
          <div class="form-field form-field--wide">
            <span>{{ t("prompts.filesLabel") }}</span>
            <small v-if="formErrors.files" class="field-error">{{ formErrors.files }}</small>
            <div class="prompt-file-workbench">
              <nav class="prompt-file-list" :aria-label="t('prompts.filesLabel')">
                <button v-for="file in fileNames" :key="file" :class="{ active: selectedFile === file, empty: fileEmpty(file) }" type="button" @click="selectedFile = file">
                  <span>{{ displayFileName(file) }}</span>
                  <small v-if="fileBadge(file)">{{ fileBadge(file) }}</small>
                  <small v-else-if="fileEmpty(file)" class="prompt-file-empty">{{ t("common.empty") }}</small>
                </button>
                <button type="button" class="prompt-file-add" @click="addFile"><Plus />{{ t("prompts.file") }}</button>
              </nav>
              <div class="prompt-editor-panel">
                <div v-if="selectedFile" class="template-editor-status">
                  <strong>{{ selectedFile }}</strong>
                  <span>{{ selectedFileStats }}</span>
                </div>
                <textarea v-if="selectedFile" v-model="draft.files[selectedFile]" class="template-editor-text" spellcheck="false" />
              </div>
              <aside v-if="selectedFile" class="prompt-actions-panel">
                <div class="template-file-meta">
                  <strong>{{ displayFileName(selectedFile) }}</strong>
                  <span>{{ fileHelp(selectedFile) }}</span>
                </div>
                <div class="prompt-actions-stack">
                  <UiButton variant="primary" type="submit" :tooltip="t('actions.save')" aria-label="Save"><Save /></UiButton>
                  <UiButton type="button" :tooltip="t('actions.aiFill')" aria-label="AI fill" @click="aiFillOpen = !aiFillOpen"><Sparkles /></UiButton>
                  <UiButton type="button" :tooltip="t('prompts.fillExample')" aria-label="Fill example" @click="fillExample(selectedFile)"><FilePlus2 /></UiButton>
                  <UiButton type="button" :tooltip="t('prompts.fillEmptyExamples')" aria-label="Fill empty examples" @click="fillEmptyExamples"><Files /></UiButton>
                  <UiButton type="button" :disabled="protectedFile(selectedFile)" :tooltip="t('prompts.rename')" aria-label="Rename" @click="renameFile"><Pencil /></UiButton>
                  <UiButton type="button" variant="danger" :disabled="protectedFile(selectedFile)" :tooltip="t('actions.delete')" aria-label="Delete file" @click="deleteFile"><Trash2 /></UiButton>
                  <UiButton v-if="!draft._draft" type="button" variant="danger" :tooltip="t('prompts.deleteTemplate')" aria-label="Delete template" @click="deleteTemplate"><Trash2 /></UiButton>
                </div>
              </aside>
            </div>
          </div>
          <div class="form-field form-field--wide">
            <details class="advanced-disclosure">
              <summary>{{ t("profiles.advancedJson") }}</summary>
              <JsonEditor v-model="draft" />
            </details>
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
import { useRoute, useRouter } from "vue-router";
import { Copy, FilePlus2, Files, Pencil, Plus, Save, Sparkles, Trash2 } from "@lucide/vue";
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

const route = useRoute();
const router = useRouter();
const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const PROMPT_SYSTEM_FILES = ["AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "MEMORY.md"];
const TEMPLATE_FILES = [...PROMPT_SYSTEM_FILES, "HEARTBEAT.md", "PROACTIVE.md"];
const TEMPLATE_FILE_ORDER = new Map(TEMPLATE_FILES.map((file, index) => [file, index]));
const EMPTY_TEMPLATE_FILES = Object.fromEntries(TEMPLATE_FILES.map((file) => [file, ""]));
const selectedId = ref("");
const draft = ref(null);
const selectedFile = ref("");
const formErrors = ref({});
const formMessage = ref("");
const exampleFiles = ref({});
const TEMPLATE_SELECTION_STORAGE_KEY = "zeroclaw.webui.selected.template";
const TEMPLATE_FILE_SELECTION_STORAGE_KEY = "zeroclaw.webui.selected.templateFile";
const aiFillOpen = ref(false);
const aiFill = ref({
  llm_profile: "",
  instruction: t("prompts.defaultAiInstruction"),
  description: "",
  files: [],
  reference_files: []
});

const fileNames = computed(() => sortedTemplateFiles(Object.keys(draft.value?.files || {})));
const llmOptions = computed(() => store.profiles.llm.map((profile) => ({ label: itemId(profile), value: itemId(profile) })));
const selectedFileStats = computed(() => {
  const content = draft.value?.files?.[selectedFile.value] || "";
  if (!content.trim()) return t("common.empty");
  return `${content.length} chars`;
});

watch(
  () => store.templates,
  (templates) => {
    const routeTemplate = queryString(route.query.template);
    const storedTemplate = localStorage.getItem(TEMPLATE_SELECTION_STORAGE_KEY) || "";
    const targetTemplate = routeTemplate || storedTemplate;
    if (targetTemplate && templates.some((template) => itemId(template) === targetTemplate) && selectedId.value !== targetTemplate) {
      selectTemplate(templates.find((template) => itemId(template) === targetTemplate), { syncRoute: !routeTemplate });
      return;
    }
    if (!draft.value && templates.length) selectTemplate(templates[0]);
  },
  { immediate: true }
);

watch(
  () => route.query.template,
  (templateId) => {
    const template = store.templates.find((item) => itemId(item) === queryString(templateId));
    if (template) selectTemplate(template, { syncRoute: false });
  }
);

watch(
  () => route.query.file,
  (file) => {
    const filename = queryString(file);
    if (filename && draft.value?.files?.[filename] !== undefined) selectedFile.value = filename;
  }
);

watch(selectedFile, (file) => {
  if (file) {
    localStorage.setItem(TEMPLATE_FILE_SELECTION_STORAGE_KEY, file);
    replaceQueryValue("file", file);
  }
});

function selectTemplate(template, options = {}) {
  selectedId.value = itemId(template);
  draft.value = clone(template);
  ensureTemplateFiles(draft.value);
  localStorage.setItem(TEMPLATE_SELECTION_STORAGE_KEY, selectedId.value);
  if (options.syncRoute !== false) replaceQueryValue("template", selectedId.value);
  selectedFile.value = initialSelectedFile(draft.value);
  formErrors.value = {};
  formMessage.value = "";
  resetAiFill();
}

function createTemplate() {
  const next = store.templates.length + 1;
  draft.value = { id: `template-${next}`, description: "", files: { ...EMPTY_TEMPLATE_FILES }, _draft: true };
  selectedId.value = "";
  replaceQueryValue("template", "");
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
  ensureTemplateFiles(copy);
  selectedId.value = "";
  replaceQueryValue("template", "");
  draft.value = copy;
  selectedFile.value = sortedTemplateFiles(Object.keys(copy.files || {}))[0] || "";
  resetAiFill();
}

async function save() {
  if (!validateTemplateForm()) return;
  const payload = clone(draft.value);
  payload.files = payload.files || {};
  ensureTemplateFiles(payload);
  delete payload._draft;
  await store.saveTemplate(payload);
  selectedId.value = payload.id;
  draft.value = payload;
  localStorage.setItem(TEMPLATE_SELECTION_STORAGE_KEY, payload.id);
  replaceQueryValue("template", payload.id);
  formErrors.value = {};
  formMessage.value = "";
}

async function deleteTemplate() {
  if (!draft.value || !(await dialog.confirm(t("confirm.deleteTemplateNamed", { id: itemId(draft.value) })))) return;
  await store.deleteTemplate(itemId(draft.value));
  localStorage.removeItem(TEMPLATE_SELECTION_STORAGE_KEY);
  localStorage.removeItem(TEMPLATE_FILE_SELECTION_STORAGE_KEY);
  replaceQueryValue("template", "");
  replaceQueryValue("file", "");
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
  replaceQueryValue("file", normalized);
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
  replaceQueryValue("file", normalized);
  formErrors.value = { ...formErrors.value, files: "" };
  formMessage.value = firstError(formErrors.value) ? t("validation.fixFields") : "";
  resetAiFill();
}

async function deleteFile() {
  if (!selectedFile.value || protectedFile(selectedFile.value)) return;
  if (!(await dialog.confirm(t("confirm.deleteTemplateFileNamed", { file: selectedFile.value })))) return;
  delete draft.value.files[selectedFile.value];
  selectedFile.value = sortedTemplateFiles(Object.keys(draft.value.files || {}))[0] || "";
  replaceQueryValue("file", selectedFile.value);
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

async function loadExampleFiles() {
  if (Object.keys(exampleFiles.value).length) return exampleFiles.value;
  const result = await store.promptTemplateExamples();
  exampleFiles.value = result.files || {};
  return exampleFiles.value;
}

async function fillExample(file) {
  if (!file || !draft.value?.files) return;
  const examples = await loadExampleFiles();
  draft.value.files[file] = examples[file] || "";
}

async function fillEmptyExamples() {
  if (!draft.value?.files) return;
  const examples = await loadExampleFiles();
  for (const file of TEMPLATE_FILES) {
    if (file in draft.value.files && !String(draft.value.files[file] || "").trim()) {
      draft.value.files[file] = examples[file] || "";
    }
  }
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
  if (index >= 0) return `#${index + 1}`;
  return "";
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

function ensureTemplateFiles(template) {
  if (!template.files || typeof template.files !== "object") template.files = {};
  for (const file of TEMPLATE_FILES) {
    if (!(file in template.files)) template.files[file] = "";
  }
  template.files = Object.fromEntries(sortedTemplateFiles(Object.keys(template.files)).map((file) => [file, template.files[file]]));
}

function displayFileName(file) {
  return String(file || "").replace(/\.md$/i, "");
}

function fileEmpty(file) {
  return !String(draft.value?.files?.[file] || "").trim();
}

function initialSelectedFile(template) {
  const files = template.files || {};
  const routeFile = queryString(route.query.file);
  const storedFile = localStorage.getItem(TEMPLATE_FILE_SELECTION_STORAGE_KEY) || "";
  if (routeFile && files[routeFile] !== undefined) return routeFile;
  if (storedFile && files[storedFile] !== undefined) return storedFile;
  return sortedTemplateFiles(Object.keys(files))[0] || "";
}

function sortedTemplateFiles(files) {
  return [...files].sort((left, right) => {
    const leftRank = TEMPLATE_FILE_ORDER.has(left) ? TEMPLATE_FILE_ORDER.get(left) : TEMPLATE_FILES.length;
    const rightRank = TEMPLATE_FILE_ORDER.has(right) ? TEMPLATE_FILE_ORDER.get(right) : TEMPLATE_FILES.length;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.localeCompare(right);
  });
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
