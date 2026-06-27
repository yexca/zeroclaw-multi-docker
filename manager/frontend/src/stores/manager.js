import { defineStore } from "pinia";
import { api, clone, itemId } from "../lib/api.js";

const DEFAULT_AGENT = {
  id: "agent1",
  host_port: 42641,
  llm_profile: "",
  matrix_profile: "",
  mcp_profile: "",
  vision_profile: "",
  prompt_template: "",
  external_peers: [],
  skill_bundles: ["core"],
  image: "ghcr.io/zeroclaw-labs/zeroclaw:v0.8.1-debian"
};

const DEFAULT_PROFILE = {
  llm: {
    id: "openai-default",
    provider_family: "openai",
    provider_alias: "default",
    model: "gpt-5.4",
    base_url: "https://api.openai.com/v1",
    wire_api: "chat_completions",
    timeout_secs: 120
  },
  vision: {
    id: "vision-default",
    provider_family: "custom",
    provider_alias: "vision",
    model: "gpt-4o",
    base_url: "https://api.openai.com/v1",
    wire_api: "chat_completions",
    timeout_secs: 120,
    max_images: 4,
    max_image_size_mb: 5,
    max_image_turns: 2,
    allow_remote_fetch: false
  },
  matrix: {
    id: "matrix-default",
    homeserver: "https://matrix.org",
    user_id: "",
    device_id: "",
    password: "",
    recovery_key: "",
    allowed_rooms: []
  },
  mcp: {
    id: "mcp-home",
    url: "http://host.docker.internal:8000",
    enabled: true
  }
};

export const useManagerStore = defineStore("manager", {
  state: () => ({
    config: null,
    dashboard: null,
    images: null,
    resources: null,
    validation: null,
    loading: false,
    busy: false,
    notice: "",
    error: ""
  }),
  getters: {
    agents: (state) => state.config?.agents || [],
    profiles: (state) => state.config?.profiles || { llm: [], vision: [], matrix: [], mcp: [] },
    templates: (state) => state.config?.prompt_templates || [],
    skillBundles: (state) => state.config?.skill_bundles || [],
    skillsConfig: (state) => state.config?.skills || {}
  },
  actions: {
    setNotice(message) {
      this.notice = message;
      this.error = "";
    },
    setError(error) {
      this.error = error?.message || String(error);
    },
    async loadConfig() {
      this.loading = true;
      try {
        this.config = await api("/api/config");
      } catch (error) {
        this.setError(error);
      } finally {
        this.loading = false;
      }
    },
    async saveConfig(config) {
      this.busy = true;
      try {
        this.config = await api("/api/config", { method: "PUT", body: config });
        this.setNotice("Configuration saved.");
      } catch (error) {
        this.setError(error);
        throw error;
      } finally {
        this.busy = false;
      }
    },
    async validateConfig() {
      this.validation = await api("/api/config/validate");
      return this.validation;
    },
    newAgent() {
      const next = this.agents.length + 1;
      return { ...clone(DEFAULT_AGENT), id: `agent${next}`, host_port: 42640 + next };
    },
    async saveAgent(agent) {
      const id = itemId(agent);
      const exists = this.agents.some((item) => itemId(item) === id);
      const path = exists ? `/api/agents/${encodeURIComponent(id)}` : "/api/agents";
      const method = exists ? "PUT" : "POST";
      await api(path, { method, body: agent });
      await this.loadConfig();
      this.setNotice(`Agent ${id} saved.`);
    },
    async deleteAgent(id) {
      await api(`/api/agents/${encodeURIComponent(id)}`, { method: "DELETE" });
      await this.loadConfig();
      this.setNotice(`Agent ${id} deleted.`);
    },
    async controlAgent(id, operation) {
      await api(`/api/agents/${encodeURIComponent(id)}/${operation}`, { method: "POST" });
      this.setNotice(`${operation} sent to ${id}.`);
      await this.loadDashboard();
    },
    newProfile(kind) {
      const base = clone(DEFAULT_PROFILE[kind] || { id: `${kind}-default` });
      const count = this.profiles[kind]?.length || 0;
      base.id = `${kind}-${count + 1}`;
      return base;
    },
    async saveProfile(kind, profile) {
      const id = itemId(profile);
      const exists = (this.profiles[kind] || []).some((item) => itemId(item) === id);
      const path = exists ? `/api/profiles/${kind}/${encodeURIComponent(id)}` : `/api/profiles/${kind}`;
      const method = exists ? "PUT" : "POST";
      await api(path, { method, body: profile });
      await this.loadConfig();
      this.setNotice(`${kind.toUpperCase()} profile ${id} saved.`);
    },
    async deleteProfile(kind, id) {
      await api(`/api/profiles/${kind}/${encodeURIComponent(id)}`, { method: "DELETE" });
      await this.loadConfig();
      this.setNotice(`${kind.toUpperCase()} profile ${id} deleted.`);
    },
    async saveTemplate(template) {
      const id = itemId(template);
      const exists = this.templates.some((item) => itemId(item) === id);
      const path = exists ? `/api/prompt-templates/${encodeURIComponent(id)}` : "/api/prompt-templates";
      const method = exists ? "PUT" : "POST";
      await api(path, { method, body: template });
      await this.loadConfig();
      this.setNotice(`Prompt template ${id} saved.`);
    },
    async loadDashboard() {
      this.dashboard = await api("/api/dashboard");
    },
    async loadImages() {
      this.images = await api("/api/docker/images");
    },
    async loadResources() {
      this.resources = await api("/api/docker/resources");
    },
    async exportConfig(includeSecrets = false) {
      const result = await api("/api/export", { method: "POST", body: { include_secrets: includeSecrets } });
      this.setNotice("Generated export written.");
      return result;
    }
  }
});
