<template>
  <section class="view-stack">
    <PageHeader :title="t('skills.title')" :description="t('skills.subtitle')">
      <UiButton @click="newBundle"><Plus />{{ t("skills.bundle") }}</UiButton>
      <UiButton :disabled="!selectedBundleId" @click="newSkill"><Plus />{{ t("skills.skill") }}</UiButton>
      <UiButton :disabled="!selectedSkillName" @click="newSupportFile"><FilePlus2 />{{ t("skills.newTextFile") }}</UiButton>
    </PageHeader>

    <div class="skills-workbench">
      <UiCard title="Skill explorer" description="Select a node to edit its details.">
        <div class="skill-tree">
          <button :class="treeClass('runtime')" type="button" @click="selectRuntime">
            <Settings2 />
            <span>
              <strong>Runtime settings</strong>
              <small>{{ skills.allow_scripts ? t("common.enabled") : t("common.disabled") }} scripts</small>
            </span>
          </button>

          <template v-for="bundle in bundles" :key="bundle.id">
            <button :class="treeClass('bundle', bundle.id)" type="button" @click="selectBundle(bundle)">
              <Package />
              <span>
                <strong>{{ bundle.id }}</strong>
                <small>{{ bundle.directory || `shared/skills/${bundle.id}` }}</small>
              </span>
            </button>

            <template v-for="skill in bundleSkills(bundle.id)" :key="`${bundle.id}/${skill.name}`">
              <button :class="treeClass('skill', bundle.id, skill.name)" class="skill-tree__skill" type="button" @click="selectSkill(bundle.id, skill.name)">
                <Wrench />
                <span>
                  <strong>{{ skill.name }}</strong>
                  <small>{{ skill.frontmatter?.description || t("skills.noDescription") }}</small>
                </span>
                <small class="skill-tree__count">{{ supportCount(bundle.id, skill.name) }}</small>
              </button>

              <template v-if="selectedBundleId === bundle.id && selectedSkillName === skill.name">
                <button :class="treeClass('skill-doc', bundle.id, skill.name)" class="skill-tree__file" type="button" @click="selectSkillDoc(bundle.id, skill.name)">
                  <FileText />
                  <span><strong>SKILL.md</strong></span>
                </button>
                <template v-for="type in supportTypes" :key="`${bundle.id}/${skill.name}/${type}`">
                  <button :class="treeClass('support-group', bundle.id, skill.name, type)" class="skill-tree__folder" type="button" @click="selectSupportGroup(bundle.id, skill.name, type)">
                    <Folder />
                    <span>
                      <strong>{{ type }}</strong>
                      <small>{{ filesFor(bundle.id, skill.name, type).length }} files</small>
                    </span>
                  </button>
                  <button
                    v-for="file in filesFor(bundle.id, skill.name, type)"
                    :key="`${bundle.id}/${skill.name}/${file}`"
                    :class="treeClass('support-file', bundle.id, skill.name, file)"
                    class="skill-tree__support"
                    type="button"
                    @click="loadSupportFile(bundle.id, skill.name, file)"
                  >
                    <component :is="fileIcon(type)" />
                    <span>
                      <strong>{{ fileName(file) }}</strong>
                      <small>{{ file }}</small>
                    </span>
                  </button>
                </template>
              </template>
            </template>

            <p v-if="loadedBundles.has(bundle.id) && !bundleSkills(bundle.id).length" class="skill-tree__empty">{{ t("skills.noSkills") }}</p>
          </template>
        </div>
      </UiCard>

      <UiCard :title="detailTitle" :description="detailDescription">
        <form v-if="selectedNode.type === 'runtime'" class="form-grid" @submit.prevent="saveRuntime">
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
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("skills.saveSettings") }}</UiButton>
          </div>
        </form>

        <form v-else-if="selectedNode.type === 'bundle' && bundleDraft" class="form-grid" @submit.prevent="saveBundle">
          <FormField v-model="bundleDraft.id" :label="t('fields.id')" :error="bundleErrors.id" required />
          <FormField v-model="bundleDraft.directory" :label="t('fields.directory')" :error="bundleErrors.directory" required />
          <FormField v-model="bundleInclude" :label="t('fields.includeSkills')" textarea wide />
          <FormField v-model="bundleExclude" :label="t('fields.excludeSkills')" textarea wide />
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("skills.saveBundle") }}</UiButton>
            <UiButton v-if="!bundleDraft._draft" type="button" variant="danger" @click="deleteBundle"><Trash2 />{{ t("actions.delete") }}</UiButton>
          </div>
          <p v-if="bundleMessage" class="field-error form-field--wide">{{ bundleMessage }}</p>
        </form>

        <form v-else-if="isSkillEditor && skillDraft" class="form-grid" @submit.prevent="saveSkillDoc">
          <FormField v-model="skillDraft.name" :label="t('fields.name')" :error="skillErrors.name" required />
          <FormField v-model="skillDraft.description" :label="t('fields.description')" />
          <FormField v-model="skillDraft.category" :label="t('fields.category')" />
          <FormField v-model="skillTags" :label="t('fields.tags')" />
          <FormField v-model="skillDraft.content" :label="t('fields.skillBody')" textarea wide />
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("skills.saveSkill") }}</UiButton>
            <UiButton v-if="!skillDraft._draft" type="button" variant="danger" @click="deleteSkillDoc"><Trash2 />{{ t("actions.archive") }}</UiButton>
          </div>
          <p v-if="skillMessage" class="field-error form-field--wide">{{ skillMessage }}</p>
        </form>

        <div v-else-if="selectedNode.type === 'support-group'" class="resource-buckets">
          <div class="profile-usage-panel">
            <strong>{{ selectedNode.supportType }}</strong>
            <span>{{ filesFor(selectedBundleId, selectedSkillName, selectedNode.supportType).length }} files in this support directory.</span>
          </div>
          <div class="button-row">
            <UiButton @click="newSupportFile"><Plus />{{ t("skills.newTextFile") }}</UiButton>
            <label class="ui-button">
              <Upload />
              {{ t("actions.upload") }}
              <input class="visually-hidden-file" type="file" @change="uploadSupportFile" />
            </label>
          </div>
          <div class="resource-row-list">
            <button
              v-for="file in filesFor(selectedBundleId, selectedSkillName, selectedNode.supportType)"
              :key="file"
              class="resource-card resource-card--button"
              type="button"
              @click="loadSupportFile(selectedBundleId, selectedSkillName, file)"
            >
              <span>
                <strong>{{ fileName(file) }}</strong>
                <span>{{ file }}</span>
              </span>
              <FileText />
            </button>
          </div>
        </div>

        <form v-else-if="selectedNode.type === 'support-file'" class="form-grid" @submit.prevent="saveSupportFile">
          <FormField v-model="supportFilePath" :label="t('fields.supportFilePath')" :error="supportErrors.path" wide required />
          <FormField v-model="supportFileContent" :label="t('fields.supportFileContent')" textarea wide />
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />{{ t("skills.saveFile") }}</UiButton>
            <UiButton type="button" @click="newSupportFile"><Plus />{{ t("skills.newTextFile") }}</UiButton>
            <label class="ui-button">
              <Upload />
              {{ t("actions.upload") }}
              <input class="visually-hidden-file" type="file" @change="uploadSupportFile" />
            </label>
            <UiButton v-if="supportFilePath" type="button" variant="danger" @click="deleteSupportFile"><Trash2 />{{ t("actions.delete") }}</UiButton>
          </div>
          <p v-if="supportMessage" class="field-error form-field--wide">{{ supportMessage }}</p>
        </form>

        <p v-else class="empty-text">{{ t("skills.empty") }}</p>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { FileCode2, FilePlus2, FileText, Folder, Image, Package, Plus, Save, Settings2, Terminal, Trash2, Upload, Wrench } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { clone, itemId } from "../lib/api.js";
import { firstError, validateRelativeDirectory, validateRequired, validateSkillBundleId, validateSupportPath, valueExists } from "../lib/validation.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const skills = reactive({});
const bundles = computed(() => store.skillBundles);
const supportTypes = ["references", "scripts", "assets"];
const selectedNode = ref({ type: "runtime" });
const selectedBundleId = ref("");
const selectedSkillName = ref("");
const supportType = ref("references");
const loadedBundles = reactive(new Set());
const skillRows = reactive({});
const skillDocs = reactive({});
const bundleDraft = ref(null);
const skillDraft = ref(null);
const supportFilePath = ref("");
const supportFileContent = ref("");
const bundleErrors = ref({});
const skillErrors = ref({});
const supportErrors = ref({});
const bundleMessage = ref("");
const skillMessage = ref("");
const supportMessage = ref("");

const isSkillEditor = computed(() => ["skill", "skill-doc"].includes(selectedNode.value.type));
const detailTitle = computed(() => {
  if (selectedNode.value.type === "runtime") return "Runtime settings";
  if (selectedNode.value.type === "bundle") return selectedBundleId.value || t("skills.bundle");
  if (isSkillEditor.value) return selectedSkillName.value || t("skills.skill");
  if (selectedNode.value.type === "support-group") return selectedNode.value.supportType || t("skills.supportFiles");
  if (selectedNode.value.type === "support-file") return supportFilePath.value || t("skills.supportFiles");
  return t("skills.title");
});
const detailDescription = computed(() => {
  if (selectedNode.value.type === "runtime") return t("skills.runtimeHelp");
  if (selectedNode.value.type === "bundle") return t("skills.bundleSettingsHelp");
  if (isSkillEditor.value) return "Edit the canonical SKILL.md frontmatter and body.";
  return t("skills.supportFilesHelp");
});

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

watch(
  () => store.skillsConfig,
  (value) => Object.assign(skills, clone(value || {})),
  { immediate: true, deep: true }
);

watch(
  bundles,
  async (rows) => {
    await Promise.all(rows.map((bundle) => loadSkillsForBundle(bundle.id)));
    if (!selectedBundleId.value && rows.length) selectBundle(rows[0]);
  },
  { immediate: true }
);

function lines(value) {
  return String(value || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function docKey(bundleId, skillName) {
  return `${bundleId}/${skillName}`;
}

function bundleSkills(bundleId) {
  return skillRows[bundleId] || [];
}

function filesFor(bundleId, skillName, type) {
  const doc = skillDocs[docKey(bundleId, skillName)];
  return (doc?.files || []).filter((file) => String(file).replace("\\", "/").startsWith(`${type}/`));
}

function supportCount(bundleId, skillName) {
  const count = supportTypes.reduce((total, type) => total + filesFor(bundleId, skillName, type).length, 0);
  return count ? `${count} files` : "SKILL only";
}

function treeClass(type, bundleId = "", skillName = "", path = "") {
  return {
    active:
      selectedNode.value.type === type &&
      (bundleId ? selectedNode.value.bundleId === bundleId : true) &&
      (skillName ? selectedNode.value.skillName === skillName : true) &&
      (path ? (selectedNode.value.path || selectedNode.value.supportType) === path : true)
  };
}

function fileIcon(type) {
  if (type === "scripts") return Terminal;
  if (type === "assets") return Image;
  if (type === "references") return FileText;
  return FileCode2;
}

function fileName(path) {
  return String(path || "").split("/").pop() || path;
}

function clearMessages() {
  bundleErrors.value = {};
  skillErrors.value = {};
  supportErrors.value = {};
  bundleMessage.value = "";
  skillMessage.value = "";
  supportMessage.value = "";
}

async function loadSkillsForBundle(bundleId) {
  if (!bundleId) return;
  const result = await store.listSkills(bundleId);
  skillRows[bundleId] = result.skills || [];
  loadedBundles.add(bundleId);
  await Promise.all(
    skillRows[bundleId].map(async (skill) => {
      try {
        skillDocs[docKey(bundleId, skill.name)] = await store.readSkill(bundleId, skill.name);
      } catch {
        skillDocs[docKey(bundleId, skill.name)] = { files: [] };
      }
    })
  );
}

function selectRuntime() {
  selectedNode.value = { type: "runtime" };
  selectedBundleId.value = "";
  selectedSkillName.value = "";
  clearMessages();
}

function selectBundle(bundle) {
  selectedNode.value = { type: "bundle", bundleId: bundle.id };
  selectedBundleId.value = bundle.id;
  selectedSkillName.value = "";
  bundleDraft.value = clone(bundle);
  skillDraft.value = null;
  supportFilePath.value = "";
  supportFileContent.value = "";
  clearMessages();
  loadSkillsForBundle(bundle.id);
}

async function selectSkill(bundleId, skillName) {
  selectedNode.value = { type: "skill", bundleId, skillName };
  selectedBundleId.value = bundleId;
  selectedSkillName.value = skillName;
  await loadSkillDraft(bundleId, skillName);
}

async function selectSkillDoc(bundleId, skillName) {
  selectedNode.value = { type: "skill-doc", bundleId, skillName };
  selectedBundleId.value = bundleId;
  selectedSkillName.value = skillName;
  await loadSkillDraft(bundleId, skillName);
}

async function loadSkillDraft(bundleId, skillName) {
  clearMessages();
  const doc = await store.readSkill(bundleId, skillName);
  skillDocs[docKey(bundleId, skillName)] = doc;
  skillDraft.value = {
    name: doc.frontmatter?.name || doc.name || skillName,
    description: doc.frontmatter?.description || "",
    category: doc.frontmatter?.category || "",
    tags: doc.frontmatter?.tags || [],
    content: doc.body || "",
    files: doc.files || []
  };
  supportFilePath.value = "";
  supportFileContent.value = "";
}

function selectSupportGroup(bundleId, skillName, type) {
  selectedNode.value = { type: "support-group", bundleId, skillName, supportType: type };
  selectedBundleId.value = bundleId;
  selectedSkillName.value = skillName;
  supportType.value = type;
  clearMessages();
}

async function loadSupportFile(bundleId, skillName, path) {
  selectedNode.value = { type: "support-file", bundleId, skillName, path };
  selectedBundleId.value = bundleId;
  selectedSkillName.value = skillName;
  supportType.value = String(path).split("/")[0] || "references";
  supportFilePath.value = path;
  clearMessages();
  try {
    const result = await store.readSupportFile(bundleId, skillName, path);
    supportFileContent.value = result.content || "";
  } catch (error) {
    supportFileContent.value = t("skills.unableToPreview", { error: error.message || error });
  }
}

async function saveRuntime() {
  const next = clone(store.config);
  next.skills = clone(skills);
  await store.saveConfig(next);
}

function newBundle() {
  const next = bundles.value.length + 1;
  selectedNode.value = { type: "bundle", bundleId: "" };
  selectedBundleId.value = "";
  selectedSkillName.value = "";
  bundleDraft.value = { id: `bundle-${next}`, directory: `shared/skills/bundle-${next}`, include: [], exclude: [], _draft: true };
  skillDraft.value = null;
  clearMessages();
}

async function saveBundle() {
  if (!validateBundleForm()) return;
  const payload = clone(bundleDraft.value);
  delete payload._draft;
  try {
    await store.saveSkillBundle(payload);
    selectedBundleId.value = payload.id;
    selectedNode.value = { type: "bundle", bundleId: payload.id };
    bundleDraft.value = payload;
    await loadSkillsForBundle(payload.id);
    clearMessages();
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
    selectedNode.value = { type: "runtime" };
  }
}

function newSkill() {
  if (!selectedBundleId.value) return;
  selectedNode.value = { type: "skill", bundleId: selectedBundleId.value, skillName: "" };
  selectedSkillName.value = "";
  skillDraft.value = {
    name: "new-skill",
    description: "",
    category: "",
    tags: [],
    content: t("skills.newSkillContent"),
    files: [],
    _draft: true
  };
  clearMessages();
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
  try {
    if (skillDraft.value._draft) {
      await store.createSkill(selectedBundleId.value, payload);
    } else {
      await store.saveSkill(selectedBundleId.value, selectedSkillName.value, payload);
    }
    await loadSkillsForBundle(selectedBundleId.value);
    selectedSkillName.value = payload.name;
    await selectSkillDoc(selectedBundleId.value, payload.name);
  } catch (error) {
    skillMessage.value = error.message || String(error);
  }
}

function validateSkillForm() {
  const errors = {};
  validateSkillBundleId(errors, "name", skillDraft.value?.name, t("validation.invalidSkillBundleId", { field: t("fields.name") }));
  if (bundleSkills(selectedBundleId.value).some((skill) => (skill.name || itemId(skill)) === skillDraft.value?.name && skillDraft.value.name !== selectedSkillName.value)) {
    errors.name = t("validation.duplicateValue", { field: t("fields.name") });
  }
  skillErrors.value = errors;
  skillMessage.value = firstError(errors) ? t("validation.fixFields") : "";
  return !skillMessage.value;
}

async function deleteSkillDoc() {
  if (!selectedSkillName.value || !(await dialog.confirm(t("confirm.archiveSkillNamed", { name: selectedSkillName.value })))) return;
  await store.deleteSkill(selectedBundleId.value, selectedSkillName.value);
  skillDraft.value = null;
  selectedSkillName.value = "";
  await loadSkillsForBundle(selectedBundleId.value);
  selectedNode.value = { type: "bundle", bundleId: selectedBundleId.value };
}

function newSupportFile() {
  if (!selectedBundleId.value || !selectedSkillName.value) return;
  const type = selectedNode.value.supportType || supportType.value || "references";
  const extension = type === "scripts" ? "sh" : type === "assets" ? "txt" : "md";
  supportType.value = type;
  supportFilePath.value = `${type}/new-file.${extension}`;
  supportFileContent.value = "";
  selectedNode.value = { type: "support-file", bundleId: selectedBundleId.value, skillName: selectedSkillName.value, path: supportFilePath.value };
  clearMessages();
}

async function saveSupportFile() {
  if (!validateSupportForm()) return;
  const savedPath = supportFilePath.value;
  try {
    await store.saveSupportFile(selectedBundleId.value, selectedSkillName.value, savedPath, supportFileContent.value);
    await loadSkillDraft(selectedBundleId.value, selectedSkillName.value);
    await loadSkillsForBundle(selectedBundleId.value);
    await loadSupportFile(selectedBundleId.value, selectedSkillName.value, savedPath);
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
  await loadSkillDraft(selectedBundleId.value, selectedSkillName.value);
  await loadSkillsForBundle(selectedBundleId.value);
  selectSupportGroup(selectedBundleId.value, selectedSkillName.value, supportType.value);
  supportFilePath.value = "";
  supportFileContent.value = "";
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
  if (!file || !selectedBundleId.value || !selectedSkillName.value) return;
  const type = selectedNode.value.supportType || supportType.value || "references";
  const path = `${type}/${file.name}`;
  supportType.value = type;
  supportFilePath.value = path;
  if (!validateSupportForm()) return;
  try {
    const content = await fileToBase64(file);
    await store.uploadSupportFile(selectedBundleId.value, selectedSkillName.value, path, content);
    await loadSkillDraft(selectedBundleId.value, selectedSkillName.value);
    await loadSkillsForBundle(selectedBundleId.value);
    await loadSupportFile(selectedBundleId.value, selectedSkillName.value, path);
  } catch (error) {
    supportMessage.value = error.message || String(error);
  }
  event.target.value = "";
}
</script>
