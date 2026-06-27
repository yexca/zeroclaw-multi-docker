import { createRouter, createWebHashHistory } from "vue-router";
import DashboardView from "../views/DashboardView.vue";
import AgentsView from "../views/AgentsView.vue";
import ProfilesView from "../views/ProfilesView.vue";
import SkillsView from "../views/SkillsView.vue";
import PromptsView from "../views/PromptsView.vue";
import ImagesView from "../views/ImagesView.vue";
import ResourcesView from "../views/ResourcesView.vue";
import ExportView from "../views/ExportView.vue";

export const routes = [
  { path: "/", redirect: "/agents" },
  { path: "/dashboard", name: "dashboard", component: DashboardView, meta: { label: "Dashboard" } },
  { path: "/agents", name: "agents", component: AgentsView, meta: { label: "Agents" } },
  { path: "/profiles/:kind", name: "profiles", component: ProfilesView, meta: { label: "Profiles" } },
  { path: "/skills", name: "skills", component: SkillsView, meta: { label: "Skills" } },
  { path: "/prompts", name: "prompts", component: PromptsView, meta: { label: "Prompts" } },
  { path: "/images", name: "images", component: ImagesView, meta: { label: "Images" } },
  { path: "/resources", name: "resources", component: ResourcesView, meta: { label: "Resources" } },
  { path: "/export", name: "export", component: ExportView, meta: { label: "Export" } }
];

export const router = createRouter({
  history: createWebHashHistory(),
  routes
});
