<template>
  <section class="view-stack">
    <PageHeader title="Skills" description="Manage runtime skill settings and bundle metadata.">
      <UiButton v-if="selectedTab === 'runtime'" variant="primary" @click="save"><Save />Save settings</UiButton>
    </PageHeader>

    <div class="segment-tabs page-tabs">
      <button v-for="tab in tabs" :key="tab.id" :class="{ active: selectedTab === tab.id }" @click="selectedTab = tab.id">
        {{ tab.label }}
      </button>
    </div>

    <div v-if="selectedTab === 'runtime'" class="tab-panel">
      <UiCard title="Runtime settings" description="Global runtime behavior for skill loading and Open Skills.">
        <div class="form-grid">
          <label class="check-row form-field--wide">
            <input v-model="skills.allow_scripts" type="checkbox" />
            <span>Allow skill scripts</span>
          </label>
          <label class="check-row form-field--wide">
            <input v-model="skills.open_skills_enabled" type="checkbox" />
            <span>Open Skills enabled</span>
          </label>
          <FormField v-model="skills.registry_url" label="Registry URL" wide />
          <FormField v-model="skills.prompt_injection_mode" label="Prompt injection mode" />
        </div>
      </UiCard>
    </div>

    <div v-else-if="selectedTab === 'bundles'" class="tab-panel">
      <UiCard title="Bundles">
        <template #actions>
          <UiButton @click="newBundle"><Plus />Bundle</UiButton>
        </template>
        <div class="item-list">
          <button v-for="bundle in bundles" :key="bundle.id" :class="{ active: selectedBundleId === bundle.id }" @click="selectBundle(bundle)">
            <strong>{{ bundle.id }}</strong>
            <span>{{ bundle.directory }}</span>
          </button>
        </div>
        <form v-if="bundleDraft" class="form-grid bundle-form" @submit.prevent="saveBundle">
          <FormField v-model="bundleDraft.id" label="ID" />
          <FormField v-model="bundleDraft.directory" label="Directory" />
          <FormField v-model="bundleInclude" label="Include" textarea wide />
          <FormField v-model="bundleExclude" label="Exclude" textarea wide />
          <div class="button-row form-field--wide">
            <UiButton variant="primary" type="submit"><Save />Save bundle</UiButton>
            <UiButton v-if="!bundleDraft._draft" variant="danger" @click="deleteBundle"><Trash2 />Delete</UiButton>
          </div>
        </form>
      </UiCard>
    </div>

    <div v-else-if="selectedTab === 'library'" class="tab-panel">
      <UiCard title="Skill library" description="Edit canonical SKILL.md content in the selected bundle.">
        <template #actions>
          <UiButton :disabled="!selectedBundleId" @click="newSkill"><Plus />Skill</UiButton>
        </template>
        <div class="skill-library-layout">
          <div class="item-list">
            <button v-for="skill in skillsList" :key="skill.name" :class="{ active: selectedSkillName === skill.name }" @click="selectSkill(skill.name)">
              <strong>{{ skill.name }}</strong>
              <span>{{ skill.frontmatter?.description || "No description" }}</span>
            </button>
            <p v-if="!skillsList.length" class="empty-text">No skills loaded for this bundle.</p>
          </div>
          <form v-if="skillDraft" class="form-grid" @submit.prevent="saveSkillDoc">
            <FormField v-model="skillDraft.name" label="Name" />
            <FormField v-model="skillDraft.description" label="Description" />
            <FormField v-model="skillDraft.category" label="Category" />
            <FormField v-model="skillTags" label="Tags" />
            <FormField v-model="skillDraft.content" label="SKILL.md body" textarea wide />
            <div class="button-row form-field--wide">
              <UiButton variant="primary" type="submit"><Save />Save skill</UiButton>
              <UiButton v-if="!skillDraft._draft" variant="danger" @click="deleteSkillDoc"><Trash2 />Archive</UiButton>
            </div>
          </form>
          <p v-else class="empty-text">Select or create a skill.</p>
        </div>
      </UiCard>
    </div>

    <div v-else class="tab-panel">
      <UiCard title="Support files" description="References, scripts, and assets for the selected skill.">
        <div v-if="selectedBundleId && selectedSkillName" class="support-file-layout">
          <aside>
            <div class="segment-tabs compact-tabs">
              <button v-for="type in supportTypes" :key="type" :class="{ active: supportType === type }" @click="supportType = type">
                {{ type }}
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
              <p v-if="!supportFilesForType.length" class="empty-text">No files in {{ supportType }}.</p>
            </div>
          </aside>
          <form class="form-grid" @submit.prevent="saveSupportFile">
            <FormField v-model="supportFilePath" label="File path" wide />
            <FormField v-model="supportFileContent" label="Content" textarea wide />
            <div class="button-row form-field--wide">
              <UiButton variant="primary" type="submit"><Save />Save file</UiButton>
              <UiButton type="button" @click="newSupportFile"><Plus />New text file</UiButton>
              <UiButton v-if="supportFilePath" type="button" variant="danger" @click="deleteSupportFile"><Trash2 />Delete</UiButton>
            </div>
            <div class="form-field form-field--wide">
              <span>Upload file</span>
              <input type="file" @change="uploadSupportFile" />
            </div>
          </form>
        </div>
        <p v-else class="empty-text">Select a bundle and skill in Skill library first.</p>
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
import { clone } from "../lib/api.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const skills = reactive({});
const bundles = computed(() => store.skillBundles);
const selectedTab = ref("runtime");
const tabs = [
  { id: "runtime", label: "Runtime settings" },
  { id: "bundles", label: "Bundles" },
  { id: "library", label: "Skill library" },
  { id: "support", label: "Support files" }
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
  loadSkills();
}

function newBundle() {
  const next = bundles.value.length + 1;
  selectedBundleId.value = "";
  bundleDraft.value = { id: `bundle-${next}`, directory: `shared/skills/bundle-${next}`, include: [], exclude: [], _draft: true };
}

async function saveBundle() {
  const payload = clone(bundleDraft.value);
  delete payload._draft;
  await store.saveSkillBundle(payload);
  selectedBundleId.value = payload.id;
  bundleDraft.value = payload;
}

async function deleteBundle() {
  if (bundleDraft.value && confirm(`Delete skill bundle ${bundleDraft.value.id}?`)) {
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
}

function newSkill() {
  selectedSkillName.value = "";
  skillDraft.value = {
    name: "new-skill",
    description: "",
    category: "",
    tags: [],
    content: "# new-skill\n\nDescribe when and how to use this skill.\n",
    _draft: true
  };
}

async function saveSkillDoc() {
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
    await store.createSkill(selectedBundleId.value, payload);
  } else {
    await store.saveSkill(selectedBundleId.value, selectedSkillName.value, payload);
  }
  await loadSkills();
  selectedSkillName.value = payload.name;
  skillDraft.value = payload;
  await selectSkill(payload.name);
}

async function deleteSkillDoc() {
  if (!selectedSkillName.value || !confirm(`Archive skill ${selectedSkillName.value}?`)) return;
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
}

async function loadSupportFile(path) {
  supportFilePath.value = path;
  try {
    const result = await store.readSupportFile(selectedBundleId.value, selectedSkillName.value, path);
    supportFileContent.value = result.content || "";
  } catch (error) {
    supportFileContent.value = `Unable to preview this file as UTF-8 text.\n\n${error.message || error}`;
  }
}

async function saveSupportFile() {
  await store.saveSupportFile(selectedBundleId.value, selectedSkillName.value, supportFilePath.value, supportFileContent.value);
  await selectSkill(selectedSkillName.value);
  supportFilePath.value ||= `${supportType.value}/new-file.md`;
}

async function deleteSupportFile() {
  if (!supportFilePath.value || !confirm(`Delete ${supportFilePath.value}?`)) return;
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
  const content = await fileToBase64(file);
  await store.uploadSupportFile(selectedBundleId.value, selectedSkillName.value, path, content);
  await selectSkill(selectedSkillName.value);
  supportFilePath.value = path;
  try {
    await loadSupportFile(path);
  } catch (_error) {
    supportFileContent.value = "";
  }
  event.target.value = "";
}
</script>
