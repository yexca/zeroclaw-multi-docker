<template>
  <section class="view-stack">
    <PageHeader title="Dashboard" description="Runtime state, quick controls, and recent manager activity.">
      <UiButton variant="primary" @click="store.loadDashboard"><RefreshCw />Refresh</UiButton>
    </PageHeader>

    <div class="metric-grid">
      <UiCard title="Configured agents"><strong class="metric-value">{{ store.agents.length }}</strong></UiCard>
      <UiCard title="Running agents"><strong class="metric-value">{{ runningCount }}</strong></UiCard>
      <UiCard title="Profiles"><strong class="metric-value">{{ profileCount }}</strong></UiCard>
      <UiCard title="Skill bundles"><strong class="metric-value">{{ store.skillBundles.length }}</strong></UiCard>
    </div>

    <UiCard title="Agents" description="Docker-backed rows appear after workspace initialization.">
      <div class="data-table">
        <div class="data-row data-row--head"><span>Agent</span><span>Status</span><span>Image</span><span>Actions</span></div>
        <div v-for="agent in dashboardAgents" :key="agent.id || agent.name" class="data-row">
          <span><strong>{{ agent.id || agent.name }}</strong></span>
          <span><mark :class="statusClass(agent.state || agent.status)">{{ agent.state || agent.status || "unknown" }}</mark></span>
          <span>{{ agent.image || "-" }}</span>
          <span class="inline-actions">
            <UiButton icon @click="store.controlAgent(agent.id || agent.name, 'start')"><Play /></UiButton>
            <UiButton icon @click="store.controlAgent(agent.id || agent.name, 'restart')"><RotateCw /></UiButton>
          </span>
        </div>
        <p v-if="!dashboardAgents.length" class="empty-text">No runtime rows loaded yet.</p>
      </div>
    </UiCard>

    <UiCard title="Validation">
      <div class="button-row">
        <UiButton @click="validate"><ShieldCheck />Validate config</UiButton>
      </div>
      <pre v-if="store.validation" class="code-block">{{ JSON.stringify(store.validation, null, 2) }}</pre>
    </UiCard>
  </section>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { Play, RefreshCw, RotateCw, ShieldCheck } from "@lucide/vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";
import UiCard from "../components/UiCard.vue";
import { useManagerStore } from "../stores/manager.js";

const store = useManagerStore();
const dashboardAgents = computed(() => store.dashboard?.agents || []);
const runningCount = computed(() => dashboardAgents.value.filter((agent) => String(agent.state || agent.status).includes("running")).length);
const profileCount = computed(() => Object.values(store.profiles).reduce((total, rows) => total + rows.length, 0));

function statusClass(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("running")) return "good";
  if (normalized.includes("error") || normalized.includes("exited")) return "bad";
  return "";
}

async function validate() {
  await store.validateConfig();
}

onMounted(() => store.loadDashboard().catch((error) => store.setError(error)));
</script>
