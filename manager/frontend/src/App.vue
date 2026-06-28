<template>
  <div class="app-frame">
    <aside class="sidebar">
      <RouterLink class="brand" to="/dashboard">
        <img class="brand-mark" src="/favicon.svg" alt="" aria-hidden="true" />
        <span>
          <strong>ZeroClaw</strong>
          <small>Dockyard</small>
        </span>
      </RouterLink>

      <nav class="nav-list" :aria-label="t('nav.label')">
        <RouterLink v-for="item in navItems" :key="item.to" class="nav-link" :to="item.to">
          <component :is="item.icon" aria-hidden="true" />
          <span>{{ t(item.labelKey) }}</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="main-surface">
      <header class="topbar">
        <div class="status-strip">
          <span :class="['status-dot', store.error ? 'danger' : '']"></span>
          <span>{{ t("app.status") }}</span>
        </div>
        <div class="topbar-actions">
          <details class="toolbar-menu">
            <summary :title="t('preferences.language')" :aria-label="t('preferences.language')"><Languages /></summary>
            <div class="toolbar-menu__panel">
              <button v-for="supportedLocale in supportedLocales" :key="supportedLocale" :class="{ active: language === supportedLocale }" type="button" @click="language = supportedLocale">
                {{ t(`preferences.languages.${supportedLocale}`) }}
              </button>
            </div>
          </details>
          <details class="toolbar-menu">
            <summary :title="t('preferences.theme')" :aria-label="t('preferences.theme')"><SunMoon /></summary>
            <div class="toolbar-menu__panel">
              <button v-for="mode in themeModes" :key="mode" :class="{ active: themeMode === mode }" type="button" @click="setTheme(mode)">
                {{ t(`preferences.themes.${mode}`) }}
              </button>
            </div>
          </details>
          <UiButton icon variant="secondary" :loading="store.loading" :aria-label="t('actions.refresh')" @click="store.loadConfig">
            <RefreshCw />
          </UiButton>
        </div>
      </header>

      <RouterView />
    </main>
    <DialogHost />
    <ToastHost />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, RouterView } from "vue-router";
import {
  Boxes,
  Bot,
  Cpu,
  FileArchive,
  FileText,
  Gauge,
  Languages,
  Network,
  Package,
  Plug,
  RefreshCw,
  Settings2,
  Sparkles,
  SunMoon
} from "@lucide/vue";
import UiButton from "./components/UiButton.vue";
import DialogHost from "./components/DialogHost.vue";
import ToastHost from "./components/ToastHost.vue";
import { useI18n } from "./composables/useI18n.js";
import { useManagerStore } from "./stores/manager.js";
import { applyThemeMode, normalizeThemeMode } from "./theme-core.mjs";
import { loadDefaultPreferences, readPreference, STORAGE_KEYS } from "./preferences.mjs";

const store = useManagerStore();
const { locale, supportedLocales, setLocale, t } = useI18n();
const themeMode = ref(normalizeThemeMode(localStorage.getItem("zeroclaw.webui.theme") || "system"));
const themeModes = ["system", "light", "dark"];
const language = computed({
  get: () => locale.value,
  set: (value) => setLocale(value)
});

const navItems = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: Gauge },
  { to: "/agents", labelKey: "nav.agents", icon: Bot },
  { to: "/profiles/llm", labelKey: "nav.llm", icon: Cpu },
  { to: "/profiles/vision", labelKey: "nav.vision", icon: Sparkles },
  { to: "/profiles/matrix", labelKey: "nav.matrix", icon: Network },
  { to: "/profiles/mcp", labelKey: "nav.mcp", icon: Plug },
  { to: "/skills", labelKey: "nav.skills", icon: Boxes },
  { to: "/prompts", labelKey: "nav.prompts", icon: FileText },
  { to: "/images", labelKey: "nav.images", icon: Package },
  { to: "/resources", labelKey: "nav.resources", icon: Settings2 },
  { to: "/export", labelKey: "nav.export", icon: FileArchive }
];

function applyTheme() {
  localStorage.setItem("zeroclaw.webui.theme", themeMode.value);
  applyThemeMode(themeMode.value, {
    documentElement: document.documentElement,
    matchMedia: window.matchMedia.bind(window)
  });
}

function setTheme(mode) {
  themeMode.value = normalizeThemeMode(mode);
  applyTheme();
}

onMounted(async () => {
  const defaults = await loadDefaultPreferences();
  if (!readPreference(localStorage, STORAGE_KEYS.language, "")) {
    setLocale(defaults.language);
  }
  if (!readPreference(localStorage, STORAGE_KEYS.theme, "")) {
    themeMode.value = normalizeThemeMode(defaults.theme);
  }
  applyTheme();
  await store.loadConfig();
});
</script>
