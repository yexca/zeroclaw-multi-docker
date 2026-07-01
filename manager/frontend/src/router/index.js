import { createRouter, createWebHashHistory } from "vue-router";
import DashboardView from "../views/DashboardView.vue";
import AgentsView from "../views/AgentsView.vue";
import ProfilesView from "../views/ProfilesView.vue";
import SkillsView from "../views/SkillsView.vue";
import PromptsView from "../views/PromptsView.vue";
import AdvancedView from "../views/AdvancedView.vue";

export const routes = [
  { path: "/", redirect: "/dashboard" },
  { path: "/dashboard", name: "dashboard", component: DashboardView, meta: { label: "Dashboard" } },
  { path: "/agents", name: "agents", component: AgentsView, meta: { label: "Agents" } },
  { path: "/profiles/:kind", name: "profiles", component: ProfilesView, meta: { label: "Profiles" } },
  { path: "/skills", name: "skills", component: SkillsView, meta: { label: "Skills" } },
  { path: "/prompts", name: "prompts", component: PromptsView, meta: { label: "Prompts" } },
  { path: "/advanced", redirect: () => `/advanced/${localStorage.getItem("zeroclaw.webui.selected.advanced") || "images"}` },
  { path: "/advanced/:section", name: "advanced", component: AdvancedView, meta: { label: "Advanced" } },
  { path: "/images", redirect: "/advanced/images" },
  { path: "/resources", redirect: "/advanced/resources" },
  { path: "/export", redirect: "/advanced/export" }
];

export const router = createRouter({
  history: createWebHashHistory("/"),
  routes
});
