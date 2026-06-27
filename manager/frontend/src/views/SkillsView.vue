<template>
  <section class="view-stack">
    <PageHeader title="Skills" description="Manage runtime skill settings and bundle metadata.">
      <UiButton variant="primary" @click="save"><Save />Save settings</UiButton>
    </PageHeader>

    <div class="split-panels">
      <UiCard title="Runtime settings">
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
const selectedBundleId = ref("");
const bundleDraft = ref(null);

const bundleInclude = computed({
  get: () => (bundleDraft.value?.include || []).join("\n"),
  set: (value) => (bundleDraft.value.include = lines(value))
});

const bundleExclude = computed({
  get: () => (bundleDraft.value?.exclude || []).join("\n"),
  set: (value) => (bundleDraft.value.exclude = lines(value))
});

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
</script>
