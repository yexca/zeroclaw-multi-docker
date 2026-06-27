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
        <div class="data-table">
          <div class="data-row data-row--head"><span>ID</span><span>Directory</span><span>Include</span><span>Exclude</span></div>
          <div v-for="bundle in bundles" :key="bundle.id" class="data-row">
            <span><strong>{{ bundle.id }}</strong></span>
            <span>{{ bundle.directory }}</span>
            <span>{{ (bundle.include || []).join(", ") || "*" }}</span>
            <span>{{ (bundle.exclude || []).join(", ") || "-" }}</span>
          </div>
        </div>
      </UiCard>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, watch } from "vue";
import { Save } from "@lucide/vue";
import FormField from "../components/FormField.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { clone } from "../lib/api.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const skills = reactive({});
const bundles = computed(() => store.skillBundles);

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
</script>
