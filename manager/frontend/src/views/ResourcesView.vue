<template>
  <section class="view-stack">
    <PageHeader title="Docker Resources" description="Containers, networks, and volumes classified by manager ownership.">
      <UiButton variant="primary" @click="store.loadResources"><RefreshCw />Refresh</UiButton>
    </PageHeader>

    <UiCard title="Resource payload">
      <pre class="code-block">{{ JSON.stringify(store.resources || {}, null, 2) }}</pre>
    </UiCard>
  </section>
</template>

<script setup>
import { onMounted } from "vue";
import { RefreshCw } from "@lucide/vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
onMounted(() => store.loadResources().catch((error) => store.setError(error)));
</script>
