<template>
  <section class="view-stack">
    <nav class="segment-tabs page-tabs advanced-tabs" :aria-label="t('advanced.tabsLabel')">
      <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="selectTab(tab.key)">
        <component :is="tab.icon" aria-hidden="true" />
        <span>{{ tab.label }}</span>
      </button>
    </nav>

    <component :is="activeComponent" />
  </section>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { FileArchive, Package, Settings2 } from "@lucide/vue";
import ImagesView from "./ImagesView.vue";
import ResourcesView from "./ResourcesView.vue";
import ExportView from "./ExportView.vue";
import { useI18n } from "../composables/useI18n.js";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const tabs = computed(() => [
  { key: "images", label: t("nav.images"), icon: Package, component: ImagesView },
  { key: "resources", label: t("nav.resources"), icon: Settings2, component: ResourcesView },
  { key: "export", label: t("nav.export"), icon: FileArchive, component: ExportView }
]);

const activeTab = computed(() => {
  const section = String(route.params.section || "");
  return tabs.value.some((tab) => tab.key === section) ? section : "images";
});

const activeComponent = computed(() => tabs.value.find((tab) => tab.key === activeTab.value)?.component || ImagesView);

function selectTab(section) {
  router.push(`/advanced/${section}`);
}
</script>
