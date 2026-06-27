<template>
  <section class="view-stack">
    <PageHeader title="Images" description="Inspect ZeroClaw runtime images and local derived variants.">
      <UiButton variant="primary" @click="store.loadImages"><RefreshCw />Refresh</UiButton>
    </PageHeader>

    <UiCard title="Docker images">
      <div class="data-table">
        <div class="data-row data-row--head"><span>Reference</span><span>Status</span><span>ID</span><span>Size</span></div>
        <div v-for="image in rows" :key="image.reference || image.id" class="data-row">
          <span><strong>{{ image.reference || image.repo_tags?.[0] || "untagged" }}</strong></span>
          <span><mark :class="image.present === false ? 'bad' : 'good'">{{ image.present === false ? "missing" : "present" }}</mark></span>
          <span>{{ image.short_id || image.id || "-" }}</span>
          <span>{{ image.size || image.size_human || "-" }}</span>
        </div>
        <p v-if="!rows.length" class="empty-text">No image data loaded.</p>
      </div>
    </UiCard>
  </section>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { RefreshCw } from "@lucide/vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const rows = computed(() => store.images?.images || store.images?.rows || []);

onMounted(() => store.loadImages().catch((error) => store.setError(error)));
</script>
