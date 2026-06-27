<template>
  <div class="app-frame">
    <aside class="sidebar">
      <RouterLink class="brand" to="/agents">
        <span class="brand-mark">Z</span>
        <span>
          <strong>ZeroClaw</strong>
          <small>Dockyard</small>
        </span>
      </RouterLink>

      <nav class="nav-list" aria-label="Main navigation">
        <RouterLink v-for="item in navItems" :key="item.to" class="nav-link" :to="item.to">
          <component :is="item.icon" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="main-surface">
      <header class="topbar">
        <div class="status-strip">
          <span :class="['status-dot', store.error ? 'danger' : '']"></span>
          <span>{{ store.error || store.notice || "Local manager control surface" }}</span>
        </div>
        <div class="topbar-actions">
          <label>
            <span>Theme</span>
            <select v-model="themeMode" @change="applyTheme">
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <UiButton variant="secondary" @click="store.loadConfig">
            <RefreshCw />
            Refresh
          </UiButton>
        </div>
      </header>

      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { RouterLink, RouterView } from "vue-router";
import {
  Boxes,
  Bot,
  Cpu,
  FileArchive,
  FileText,
  Gauge,
  Image,
  Network,
  Plug,
  RefreshCw,
  Settings2,
  Sparkles
} from "@lucide/vue";
import UiButton from "./components/UiButton.vue";
import { useManagerStore } from "./stores/manager.js";
import { applyThemeMode, normalizeThemeMode } from "./theme-core.mjs";

const store = useManagerStore();
const themeMode = ref(normalizeThemeMode(localStorage.getItem("zeroclaw.webui.theme") || "system"));

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: Gauge },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/profiles/llm", label: "LLM", icon: Cpu },
  { to: "/profiles/vision", label: "Vision", icon: Sparkles },
  { to: "/profiles/matrix", label: "Matrix", icon: Network },
  { to: "/profiles/mcp", label: "MCP", icon: Plug },
  { to: "/skills", label: "Skills", icon: Boxes },
  { to: "/prompts", label: "Prompts", icon: FileText },
  { to: "/images", label: "Images", icon: Image },
  { to: "/resources", label: "Resources", icon: Settings2 },
  { to: "/export", label: "Export", icon: FileArchive }
];

function applyTheme() {
  localStorage.setItem("zeroclaw.webui.theme", themeMode.value);
  applyThemeMode(themeMode.value, {
    documentElement: document.documentElement,
    matchMedia: window.matchMedia.bind(window)
  });
}

onMounted(async () => {
  applyTheme();
  await store.loadConfig();
});
</script>
