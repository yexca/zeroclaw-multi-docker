<template>
  <section class="view-stack">
    <PageHeader :title="t('images.title')" :description="t('images.subtitle')">
      <UiButton icon variant="primary" :loading="refreshing" :aria-label="t('actions.refresh')" @click="refreshImages"><RefreshCw /></UiButton>
    </PageHeader>

    <div class="button-row">
      <UiButton variant="primary" @click="runImageAction('pull-official')"><Download />{{ t("actions.pullOfficial") }}</UiButton>
      <UiButton @click="runBuild('build-python')"><Hammer />{{ t("actions.buildPythonImage") }}</UiButton>
      <UiButton variant="danger" @click="runBuild('build-root')"><ShieldAlert />{{ t("actions.buildRootImage") }}</UiButton>
    </div>

    <UiCard :title="t('images.localImages')">
      <div class="data-table">
        <div class="data-row data-row--head">
          <span>{{ t("images.reference") }}</span>
          <span>{{ t("dashboard.table.status") }}</span>
          <span>{{ t("images.shortId") }}</span>
          <span>{{ t("images.size") }}</span>
        </div>
        <div v-for="image in rows" :key="image.reference || image.id" class="data-row">
          <span><strong>{{ image.reference || image.repo_tags?.[0] || t("images.untagged") }}</strong></span>
          <span><mark :class="image.present === false ? 'bad' : 'good'">{{ image.present === false ? t("images.missing") : t("images.present") }}</mark></span>
          <span>{{ image.short_id || image.id || "-" }}</span>
          <span>{{ image.size || image.size_human || "-" }}</span>
        </div>
        <p v-if="!rows.length" class="empty-text">{{ t("images.empty") }}</p>
      </div>
    </UiCard>

    <UiCard v-if="lastResult" :title="t('images.lastAction')">
      <pre class="code-block">{{ JSON.stringify(lastResult, null, 2) }}</pre>
    </UiCard>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { Download, Hammer, RefreshCw, ShieldAlert } from "@lucide/vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const rows = computed(() => store.images?.images || store.images?.rows || []);
const lastResult = ref(null);
const refreshing = ref(false);

async function runImageAction(action, extra = {}) {
  lastResult.value = await store.imageAction(action, extra);
}

async function runBuild(action) {
  const ok = await dialog.confirm(t(action === "build-root" ? "confirm.buildRootImage" : "confirm.buildPythonImage"));
  if (!ok) return;
  await runImageAction(action, { acknowledge_risk: true });
}

async function refreshImages() {
  refreshing.value = true;
  try {
    await store.loadImages();
  } catch (error) {
    store.setError(error);
  } finally {
    refreshing.value = false;
  }
}

onMounted(() => {
  if (!store.images) refreshImages();
});
</script>
