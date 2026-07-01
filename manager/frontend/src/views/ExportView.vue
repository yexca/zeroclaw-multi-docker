<template>
  <section class="view-stack">
    <PageHeader :title="t('export.title')" :description="t('export.subtitle')">
      <UiButton variant="primary" @click="runExport"><FileArchive />{{ t("actions.export") }}</UiButton>
    </PageHeader>

    <UiCard :title="t('export.options')" :description="modeHelp">
      <div class="export-mode">
        <label class="check-row">
          <input v-model="includeSecrets" type="checkbox" />
          <span>{{ t("export.includeSecrets") }}</span>
        </label>
        <mark :class="includeSecrets ? 'bad' : 'good'">{{ backupType }}</mark>
      </div>
    </UiCard>

    <UiCard :title="t('export.result')">
      <div v-if="result" class="export-result">
        <div class="runtime-summary">
          <div>
            <span>{{ t("export.path") }}</span>
            <strong>{{ result.path || "-" }}</strong>
          </div>
          <div>
            <span>{{ t("export.backupType") }}</span>
            <strong>{{ backupTypeForResult }}</strong>
          </div>
          <div>
            <span>{{ t("export.sections") }}</span>
            <strong>{{ t("export.topLevelSections", { count: sectionNames.length }) }}</strong>
          </div>
        </div>

        <div class="metric-grid export-counts">
          <UiCard :title="t('agents.title')"><strong class="metric-value">{{ counts.agents }}</strong></UiCard>
          <UiCard :title="t('profiles.title')"><strong class="metric-value">{{ counts.profiles }}</strong></UiCard>
          <UiCard :title="t('prompts.title')"><strong class="metric-value">{{ counts.templates }}</strong></UiCard>
          <UiCard :title="t('skills.tabs.bundles')"><strong class="metric-value">{{ counts.skillBundles }}</strong></UiCard>
        </div>

        <div class="file-chip-grid">
          <button v-for="section in sectionNames" :key="section" class="file-chip" type="button">{{ section }}</button>
        </div>

        <details class="advanced-disclosure">
          <summary>{{ t("export.rawResult") }}</summary>
          <pre class="code-block">{{ JSON.stringify(result, null, 2) }}</pre>
        </details>
      </div>
      <p v-else class="empty-text">{{ t("export.notGenerated") }}</p>
    </UiCard>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { FileArchive } from "@lucide/vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const EXPORT_INCLUDE_SECRETS_STORAGE_KEY = "zeroclaw.webui.export.includeSecrets";
const includeSecrets = ref(localStorage.getItem(EXPORT_INCLUDE_SECRETS_STORAGE_KEY) === "true");
const result = ref(null);

watch(includeSecrets, (value) => localStorage.setItem(EXPORT_INCLUDE_SECRETS_STORAGE_KEY, value ? "true" : "false"));

const backupType = computed(() => t(includeSecrets.value ? "export.fullMode" : "export.redactedMode"));
const modeHelp = computed(() => t(includeSecrets.value ? "export.fullHelp" : "export.redactedHelp"));
const backupTypeForResult = computed(() => t(result.value?.include_secrets ? "export.fullMode" : "export.redactedMode"));
const exportedConfig = computed(() => result.value?.config || {});
const sectionNames = computed(() => Object.keys(exportedConfig.value || {}));
const counts = computed(() => {
  const config = exportedConfig.value || {};
  const profiles = config.profiles && typeof config.profiles === "object" ? config.profiles : {};
  return {
    agents: Array.isArray(config.agents) ? config.agents.length : 0,
    profiles: Object.values(profiles).reduce((total, rows) => total + (Array.isArray(rows) ? rows.length : 0), 0),
    templates: Array.isArray(config.prompt_templates) ? config.prompt_templates.length : 0,
    skillBundles: Array.isArray(config.skill_bundles) ? config.skill_bundles.length : 0
  };
});

async function runExport() {
  if (includeSecrets.value && !(await dialog.confirm(t("export.secretsConfirm")))) return;
  result.value = await store.exportConfig(includeSecrets.value);
}
</script>
