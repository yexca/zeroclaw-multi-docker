<template>
  <section class="view-stack">
    <PageHeader :title="t('resources.title')" :description="t('resources.subtitle')">
      <UiButton icon variant="primary" :loading="refreshing" :aria-label="t('actions.refresh')" @click="refreshResources"><RefreshCw /></UiButton>
    </PageHeader>

    <div class="metric-grid">
      <UiCard v-for="group in groups" :key="group.kind" :title="group.title">
        <strong class="metric-value">{{ countRows(group.data) }}</strong>
        <p class="empty-text">{{ summary(group.data) }}</p>
      </UiCard>
    </div>

    <UiCard v-for="group in groups" :key="`${group.kind}-detail`" :title="group.title">
      <div class="resource-buckets">
        <details
          v-for="bucket in buckets"
          :key="bucket.id"
          class="advanced-disclosure resource-bucket"
          :open="bucketOpen(group.kind, bucket.id)"
          @toggle="setBucketOpen(group.kind, bucket.id, $event.target.open)"
        >
          <summary>{{ t(bucket.labelKey) }} / {{ rowsFor(group.data, bucket.id).length }}</summary>
          <div v-if="rowsFor(group.data, bucket.id).length" class="resource-row-list">
            <article v-for="row in rowsFor(group.data, bucket.id)" :key="resourceKey(group.kind, row)" class="resource-card">
              <div>
                <strong>{{ row.name || row.id || row.container_name || t("common.unnamed") }}</strong>
                <span>{{ row.image || row.role || row.state || row.classification || t(bucket.labelKey) }}</span>
              </div>
              <div class="button-row">
                <UiButton v-if="canAdopt(bucket.id)" @click="runAction('adopt', group.kind, row)">{{ t("actions.adopt") }}</UiButton>
                <UiButton v-if="canIgnore(bucket.id)" @click="runAction('ignore', group.kind, row)">{{ t("actions.ignore") }}</UiButton>
                <UiButton v-if="bucket.id === 'ignored' || bucket.id === 'adopted'" @click="runAction('clear', group.kind, row)">{{ t("actions.clearDecision") }}</UiButton>
                <UiButton v-if="bucket.id === 'legacy'" @click="migrate(group.kind, row)">{{ t("actions.migrate") }}</UiButton>
                <UiButton v-if="canDelete(bucket.id)" variant="danger" @click="deleteResource(group.kind, row)">{{ t("actions.delete") }}</UiButton>
              </div>
            </article>
          </div>
          <p v-else class="empty-text">{{ t("resources.emptyBucket") }}</p>
        </details>
      </div>
    </UiCard>

    <UiCard v-if="lastResult" :title="t('resources.lastAction')">
      <pre class="code-block">{{ JSON.stringify(lastResult, null, 2) }}</pre>
    </UiCard>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RefreshCw } from "@lucide/vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useDialog } from "../composables/useDialog.js";
import { useI18n } from "../composables/useI18n.js";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const { t } = useI18n();
const dialog = useDialog();
const lastResult = ref(null);
const refreshing = ref(false);
const RESOURCE_BUCKET_STORAGE_KEY = "zeroclaw.webui.resources.openBuckets";
const openBuckets = ref(loadOpenBuckets());
const buckets = [
  { id: "expected", labelKey: "resources.expected" },
  { id: "conflicts", labelKey: "resources.conflicts" },
  { id: "orphans", labelKey: "resources.orphans" },
  { id: "legacy", labelKey: "resources.untracked" },
  { id: "adopted", labelKey: "resources.adopted" },
  { id: "ignored", labelKey: "resources.ignored" }
];

const groups = computed(() => [
  { kind: "container", title: t("resources.containers"), data: store.resources?.containers || {} },
  { kind: "volume", title: t("resources.volumes"), data: store.resources?.volumes || {} },
  { kind: "network", title: t("resources.networks"), data: store.resources?.networks || {} }
]);

function rowsFor(group, bucket) {
  return Array.isArray(group?.[bucket]) ? group[bucket] : [];
}

function countRows(group) {
  return buckets.reduce((total, bucket) => total + rowsFor(group, bucket.id).length, 0);
}

function summary(group) {
  return buckets.map((bucket) => `${t(bucket.labelKey)}: ${rowsFor(group, bucket.id).length}`).join(" / ");
}

function resourceName(row) {
  return row.name || row.id || row.container_name || row.volume_name || row.network_name || "";
}

function resourceKey(kind, row) {
  return `${kind}:${resourceName(row)}:${row.classification || row.state || ""}`;
}

function canAdopt(bucket) {
  return ["legacy", "orphans", "conflicts"].includes(bucket);
}

function canIgnore(bucket) {
  return ["legacy", "orphans", "conflicts"].includes(bucket);
}

function canDelete(bucket) {
  return ["orphans", "legacy", "conflicts"].includes(bucket);
}

function bucketKey(kind, bucket) {
  return `${kind}:${bucket}`;
}

function loadOpenBuckets() {
  try {
    const parsed = JSON.parse(localStorage.getItem(RESOURCE_BUCKET_STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function bucketOpen(kind, bucket) {
  const key = bucketKey(kind, bucket);
  return openBuckets.value.length ? openBuckets.value.includes(key) : bucket === "conflicts";
}

function setBucketOpen(kind, bucket, open) {
  const key = bucketKey(kind, bucket);
  const next = new Set(openBuckets.value);
  if (open) next.add(key);
  else next.delete(key);
  openBuckets.value = [...next];
  localStorage.setItem(RESOURCE_BUCKET_STORAGE_KEY, JSON.stringify(openBuckets.value));
}

async function runAction(action, kind, row, extra = {}) {
  lastResult.value = await store.resourceAction(action, { kind, name: resourceName(row) }, extra);
}

async function refreshResources() {
  refreshing.value = true;
  try {
    await store.loadResources();
  } catch (error) {
    store.setError(error);
  } finally {
    refreshing.value = false;
  }
}

async function migrate(kind, row) {
  const target_name = await dialog.prompt(t("resources.migrateTargetPrompt"), `${resourceName(row)}-migrated`);
  if (!target_name) return;
  await runAction("migrate", kind, row, { target_name });
}

async function deleteResource(kind, row) {
  const name = resourceName(row);
  const typed = await dialog.prompt(t("resources.deleteTypeName", { name, kind: t(`resourceKinds.${kind}`) }));
  if (typed !== name) return;
  await runAction("delete", kind, row);
}

onMounted(() => {
  if (!store.resources) refreshResources();
});
</script>
