<template>
  <section class="view-stack">
    <PageHeader title="Export" description="Write generated redacted configuration under config/generated.">
      <UiButton variant="primary" @click="runExport"><FileArchive />Export</UiButton>
    </PageHeader>

    <UiCard title="Export options">
      <label class="check-row">
        <input v-model="includeSecrets" type="checkbox" />
        <span>Include secrets in local backup</span>
      </label>
      <pre v-if="result" class="code-block">{{ JSON.stringify(result, null, 2) }}</pre>
    </UiCard>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { FileArchive } from "@lucide/vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const includeSecrets = ref(false);
const result = ref(null);

async function runExport() {
  result.value = await store.exportConfig(includeSecrets.value);
}
</script>
