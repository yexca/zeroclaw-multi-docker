<template>
  <section class="view-stack">
    <PageHeader :title="t('skills.title')" :description="t('skills.subtitle')">
      <UiButton v-if="selectedTab === 'runtime'" variant="primary" @click="save"><Save />{{ t("skills.saveSettings") }}</UiButton>
    </PageHeader>

    <div class="segment-tabs page-tabs">
      <button v-for="tab in tabs" :key="tab.id" :class="{ active: selectedTab === tab.id }" @click="selectedTab = tab.id">
        {{ t(tab.labelKey) }}
      </button>
    </div>

    <div v-if="selectedTab === 'runtime'" class="tab-panel">
      <UiCard :title="t('skills.settings')" :description="t('skills.runtimeHelp')">
        <div class="form-grid">
          <label class="check-row form-field--wide">
            <input v-model="skills.allow_scripts" type="checkbox" />
            <span>{{ t("fields.allowScripts") }}</span>
          </label>
          <label class="check-row form-field--wide">
            <input v-model="skills.open_skills_enabled" type="checkbox" />
            <span>{{ t("fields.openSkillsEnabled") }}</span>
          </label>
          <FormField v-model="skills.registry_url" :label="t('fields.registryUrl')" wide />
          <FormField v-model="skills.prompt_injection_mode" :label="t('fields.promptInjectionMode')" />
        </div>
      </UiCard>
    </div>

    <div v-else-if="selectedTab === 'bundles'" class="tab-panel">
      <UiCard :title="t('skills.tabs.bundles')">
        <template #actions>
          <UiButton @click="newBundle"><Plus />{{ t("skills.bundle") }}</UiButton>
        </template>
        <div class="item-list">
          <button v-for="bundle in bundles" :key="bundle.id" :class="{ active: selectedBundleId === bundle.id }" @click="selectBundle(bundle)">
            <strong>{{ bundle.id }}</strong>
            <span>{{ bundle.directory }}</span>
          </button>
        </div>
        <form v-if="bundleDraft" class="form-grid bundle-form" @submit.prevent="saveBundle">
          <FormField v-model="bundleDraft.id" :label="t('fields.id')" :error="bundleErrors.id" required />
          <FormField v-model="bundleDraft.directory" :label="t('fields.directory')" :error="bundleErrors.directory" required />
          <FormField v-model="bundleInclude" :label="t('fields.includeSkills')" textarea wide />
          <FormField v-model="bundleExclude" :label="t('fields.excludeSkills')" textarea wide />
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("skills.saveBundle") }}</UiButton>
            <UiButton v-if="!bundleDraft._draft" variant="danger" @click="deleteBundle"><Trash2 />{{ t("actions.delete") }}</UiButton>
          </div>
          <p v-if="bundleMessage" class="field-error form-field--wide">{{ bundleMessage }}</p>
        </form>
      </UiCard>
    </div>

    <div v-else-if="selectedTab === 'library'" class="tab-panel">
      <UiCard :title="t('skills.tabs.library')" :description="t('skills.bundleSkillsHelp')">
        <template #actions>
          <UiButton :disabled="!selectedBundleId" @click="newSkill"><Plus />{{ t("skills.skill") }}</UiButton>
        </template>
        <div class="skill-library-layout">
          <div class="item-list">
            <button v-for="skill in skillsList" :key="skill.name" :class="{ active: selectedSkillName === skill.name }" @click="selectSkill(skill.name)">
              <strong>{{ skill.name }}</strong>
              <span>{{ skill.frontmatter?.description || t("skills.noDescription") }}</span>
            </button>
            <p v-if="!skillsList.length" class="empty-text">{{ t("skills.noSkillsLoaded") }}</p>
          </div>
          <form v-if="skillDraft" class="form-grid" @submit.prevent="saveSkillDoc">
            <FormField v-model="skillDraft.name" :label="t('fields.name')" :error="skillErrors.name" required />
            <FormField v-model="skillDraft.description" :label="t('fields.description')" />
            <FormField v-model="skillDraft.category" :label="t('fields.category')" />
            <FormField v-model="skillTags" :label="t('fields.tags')" />
            <FormField v-model="skillDraft.content" :label="t('fields.skillBody')" textarea wide />
            <div class="button-row form-field--wide">
              <UiButton variant="primary" type="submit"><Save />{{ t("skills.saveSkill") }}</UiButton>
              <UiButton v-if="!skillDraft._draft" variant="danger" @click="deleteSkillDoc"><Trash2 />{{ t("actions.archive") }}</UiButton>
            </div>
            <p v-if="skillMessage" class="field-error form-field--wide">{{ skillMessage }}</p>
          </form>
          <p v-else class="empty-text">{{ t("skills.emptySkill") }}</p>
        </div>
      </UiCard>
    </div>

    <div v-else class="tab-panel">
      <UiCard :title="t('skills.supportFiles')" :description="t('skills.supportFilesHelp')">
        <div v-if="selectedBundleId && selectedSkillName" class="support-file-layout">
          <aside>
            <div class="segment-tabs compact-tabs">
              <button v-for="type in supportTypes" :key="type" :class="{ active: supportType === type }" @click="supportType = type">
                {{ t(`skills.supportTypes.${type}`) }}
              </button>
            </div>
            <div class="item-list support-file-list">
              <button
                v-for="file in supportFilesForType"
                :key="file"
                :class="{ active: supportFilePath === file }"
                @click="loadSupportFile(file)"
              >
                <strong>{{ fileName(file) }}</strong>
                <span>{{ file }}</span>
              </button>
              <p v-if="!supportFilesForType.length" class="empty-text">{{ t("skills.noFilesInType", { type: t(`skills.supportTypes.${supportType}`) }) }}</p>
            </div>
          </aside>
          <form class="form-grid" @submit.prevent="saveSupportFile">
            <FormField v-model="supportFilePath" :label="t('fields.supportFilePath')" :error="supportErrors.path" wide required />
            <FormField v-model="supportFileContent" :label="t('fields.supportFileContent')" textarea wide />
            <div class="button-row form-field--wide">
              <UiButton variant="primary" type="submit"><Save />{{ t("skills.saveFile") }}</UiButton>
              <UiButton type="button" @click="newSupportFile"><Plus />{{ t("skills.newTextFile") }}</UiButton>
              <UiButton v-if="supportFilePath" type="button" variant="danger" @click="deleteSupportFile"><Trash2 />{{ t("actions.delete") }}</UiButton>
            </div>
            <p v-if="supportMessage" class="field-error form-field--wide">{{ supportMessage }}</p>
            <div class="form-field form-field--wide">
              <span>{{ t("fields.uploadFile") }}</span>
              <input type="file" @change="uploadSupportFile" />
            </div>
          </form>
        </div>
        <p v-else class="empty-text">{{ t("skills.selectBundleSkillFirst") }}</p>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Plus, Save, Trash2 } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { clone, itemId } from "../lib/api.js";
import {
  firstError,
  validateRelativeDirectory,
  validateRequired,
  validateSkillBundleId,
  validateSupportPath,
  valueExists
} from "../lib/validation.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const skills = reactive({});
const bundles = computed(() => store.skillBundles);
const selectedTab = ref("runtime");
const tabs = [
  { id: "runtime", labelKey: "skills.tabs.runtime" },
  { id: "bundles", labelKey: "skills.tabs.bundles" },
  { id: "library", labelKey: "skills.tabs.library" },
  { id: "support", labelKey: "skills.tabs.support" }
];
const selectedBundleId = ref("");
const bundleDraft = ref(null);
const skillsList = ref([]);
const selectedSkillName = ref("");
const skillDraft = ref(null);
const supportTypes = ["references", "scripts", "assets"];
const supportType = ref("references");
const supportFilePath = ref("");
const supportFileContent = ref("");
const bundleErrors = ref({});
const bundleMessage = ref("");
const skillErrors = ref({});
const skillMessage = ref("");
const supportErrors = ref({});
const supportMessage = ref("");

const bundleInclude = computed({
  get: () => (bundleDraft.value?.include || []).join("\n"),
  set: (value) => (bundleDraft.value.include = lines(value))
});

const bundleExclude = computed({
  get: () => (bundleDraft.value?.exclude || []).join("\n"),
  set: (value) => (bundleDraft.value.exclude = lines(value))
});

const skillTags = computed({
  get: () => (skillDraft.value?.tags || []).join(", "),
  set: (value) => (skillDraft.value.tags = String(value || "").split(",").map((tag) => tag.trim()).filter(Boolean))
});

const supportFilesForType = computed(() =>
  (skillDraft.value?.files || []).filter((file) => String(file).replace("\\", "/").startsWith(`${supportType.value}/`))
);

watch(
  () => store.skillsConfig,
  (value) => Object.assign(skills, clone(value || {})),
  { immediate: true, deep: true }
);

async function save() {
  const next = clone(store.config);
  next.skills = clone(skills);
  await store.saveConfig(next);
}

watch(
  bundles,
  (rows) => {
    if (!bundleDraft.value && rows.length) selectBundle(rows[0]);
  },
  { immediate: true }
);

function lines(value) {
  return String(value || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function selectBundle(bundle) {
  selectedBundleId.value = bundle.id;
  bundleDraft.value = clone(bundle);
  selectedSkillName.value = "";
  skillDraft.value = null;
  supportFilePath.value = "";
  supportFileContent.value = "";
  bundleErrors.value = {};
  bundleMessage.value = "";
  skillErrors.value = {};
  skillMessage.value = "";
  supportErrors.value = {};
  supportMessage.value = "";
  loadSkills();
}

function newBundle() {
  const next = bundles.value.length + 1;
  selectedBundleId.value = "";
  bundleDraft.value = { id: `bundle-${next}`, directory: `shared/skills/bundle-${next}`, include: [], exclude: [], _draft: true };
  bundleErrors.value = {};
  bundleMessage.value = "";
}

async function saveBundle() {
  if (!validateBundleForm()) return;
  const payload = clone(bundleDraft.value);
  delete payload._draft;
  try {
    await store.saveSkillBundle(payload);
    selectedBundleId.value = payload.id;
    bundleDraft.value = payload;
    bundleErrors.value = {};
    bundleMessage.value = "";
  } catch (error) {
    bundleMessage.value = error.message || String(error);
  }
}

function validateBundleForm() {
  const errors = {};
  validateSkillBundleId(errors, "id", bundleDraft.value?.id, t("validation.invalidSkillBundleId", { field: t("fields.id") }));
  if (valueExists(bundles.value, bundleDraft.value?.id, selectedBundleId.value)) {
    errors.id = t("validation.duplicateValue", { field: t("fields.id") });
  }
  validateRequired(errors, "directory", bundleDraft.value?.directory, t("messages.requiredField", { field: t("fields.directory") }));
  validateRelativeDirectory(errors, "directory", bundleDraft.value?.directory, t("validation.invalidSupportPath", { field: t("fields.directory") }));
  bundleErrors.value = errors;
  bundleMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  return !bundleMessage.value;
}

async function deleteBundle() {
  if (bundleDraft.value && await dialog.confirm(t("confirm.deleteSkillBundleNamed", { id: bundleDraft.value.id }))) {
    await store.deleteSkillBundle(bundleDraft.value.id);
    bundleDraft.value = null;
    selectedBundleId.value = "";
  }
}

async function loadSkills() {
  if (!selectedBundleId.value) return;
  const result = await store.listSkills(selectedBundleId.value);
  skillsList.value = result.skills || [];
}

async function selectSkill(name) {
  selectedSkillName.value = name;
  const doc = await store.readSkill(selectedBundleId.value, name);
  skillDraft.value = {
    name: doc.frontmatter?.name || doc.name || name,
    description: doc.frontmatter?.description || "",
    category: doc.frontmatter?.category || "",
    tags: doc.frontmatter?.tags || [],
    content: doc.body || "",
    files: doc.files || []
  };
  supportFilePath.value = "";
  supportFileContent.value = "";
  skillErrors.value = {};
  skillMessage.value = "";
  supportErrors.value = {};
  supportMessage.value = "";
}

function newSkill() {
  selectedSkillName.value = "";
  skillDraft.value = {
    name: "new-skill",
    description: "",
    category: "",
    tags: [],
    content: t("skills.newSkillContent"),
    _draft: true
  };
  skillErrors.value = {};
  skillMessage.value = "";
}

async function saveSkillDoc() {
  if (!validateSkillForm()) return;
  const draft = clone(skillDraft.value);
  const payload = {
    name: draft.name,
    frontmatter: {
      name: draft.name,
      description: draft.description,
      category: draft.category,
      tags: draft.tags
    },
    body: draft.content
  };
  if (skillDraft.value._draft) {
    try {
      await store.createSkill(selectedBundleId.value, payload);
    } catch (error) {
      skillMessage.value = error.message || String(error);
      return;
    }
  } else {
    try {
      await store.saveSkill(selectedBundleId.value, selectedSkillName.value, payload);
    } catch (error) {
      skillMessage.value = error.message || String(error);
      return;
    }
  }
  await loadSkills();
  selectedSkillName.value = payload.name;
  skillDraft.value = payload;
  skillErrors.value = {};
  skillMessage.value = "";
  await selectSkill(payload.name);
}

function validateSkillForm() {
  const errors = {};
  validateSkillBundleId(errors, "name", skillDraft.value?.name, t("validation.invalidSkillBundleId", { field: t("fields.name") }));
  if (skillsList.value.some((skill) => (skill.name || itemId(skill)) === skillDraft.value?.name && skillDraft.value.name !== selectedSkillName.value)) {
    errors.name = t("validation.duplicateValue", { field: t("fields.name") });
  }
  skillErrors.value = errors;
  skillMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  return !skillMessage.value;
}

async function deleteSkillDoc() {
  if (!selectedSkillName.value || !(await dialog.confirm(t("confirm.archiveSkillNamed", { name: selectedSkillName.value })))) return;
  await store.deleteSkill(selectedBundleId.value, selectedSkillName.value);
  selectedSkillName.value = "";
  skillDraft.value = null;
  await loadSkills();
}

function fileName(path) {
  return String(path || "").split("/").pop() || path;
}

function newSupportFile() {
  const extension = supportType.value === "scripts" ? "sh" : supportType.value === "assets" ? "txt" : "md";
  supportFilePath.value = `${supportType.value}/new-file.${extension}`;
  supportFileContent.value = "";
  supportErrors.value = {};
  supportMessage.value = "";
}

async function loadSupportFile(path) {
  supportFilePath.value = path;
  supportErrors.value = {};
  supportMessage.value = "";
  try {
    const result = await store.readSupportFile(selectedBundleId.value, selectedSkillName.value, path);
    supportFileContent.value = result.content || "";
  } catch (error) {
    supportFileContent.value = t("skills.unableToPreview", { error: error.message || error });
  }
}

async function saveSupportFile() {
  if (!validateSupportForm()) return;
  try {
    await store.saveSupportFile(selectedBundleId.value, selectedSkillName.value, supportFilePath.value, supportFileContent.value);
    await selectSkill(selectedSkillName.value);
    supportFilePath.value ||= `${supportType.value}/new-file.md`;
    supportErrors.value = {};
    supportMessage.value = "";
  } catch (error) {
    supportMessage.value = error.message || String(error);
  }
}

function validateSupportForm() {
  const errors = {};
  validateSupportPath(errors, "path", supportFilePath.value, supportType.value, t("validation.invalidSupportPath", { field: t("fields.supportFilePath") }));
  supportErrors.value = errors;
  supportMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  return !supportMessage.value;
}

async function deleteSupportFile() {
  if (!supportFilePath.value || !(await dialog.confirm(t("confirm.deleteSkillFileNamed", { path: supportFilePath.value })))) return;
  await store.deleteSupportFile(selectedBundleId.value, selectedSkillName.value, supportFilePath.value);
  supportFilePath.value = "";
  supportFileContent.value = "";
  await selectSkill(selectedSkillName.value);
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function uploadSupportFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const path = `${supportType.value}/${file.name}`;
  const errors = {};
  validateSupportPath(errors, "path", path, supportType.value, t("validation.invalidSupportPath", { field: t("fields.supportFilePath") }));
  supportErrors.value = errors;
  supportMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  if (supportMessage.value) return;
  try {
    const content = await fileToBase64(file);
    await store.uploadSupportFile(selectedBundleId.value, selectedSkillName.value, path, content);
    await selectSkill(selectedSkillName.value);
    supportFilePath.value = path;
    await loadSupportFile(path);
  } catch (error) {
    supportMessage.value = error.message || String(error);
    supportFileContent.value = "";
  }
  event.target.value = "";
}
</script>
