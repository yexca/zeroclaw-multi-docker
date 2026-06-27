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
    async agentAction(id, action, body = undefined) {
      const result = await api(`/api/agents/${encodeURIComponent(id)}/${action}`, {
        method: "POST",
        body: body || {}
      });
      this.setNotice(`${action} completed for ${id}.`);
      return result;
    },
    async getAgentStatus(id) {
      return api(`/api/agents/${encodeURIComponent(id)}/status`);
    },
    async getAgentLogs(id, tail = 200) {
      return api(`/api/agents/${encodeURIComponent(id)}/logs?tail=${encodeURIComponent(tail)}`);
    },
    async getAgentPreview(id) {
      return api(`/api/agents/${encodeURIComponent(id)}/config-preview`);
    },
    async getAgentEnv(id) {
      return api(`/api/agents/${encodeURIComponent(id)}/env`);
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
    async testLlmProfile(profile) {
      const result = await api("/api/profiles/llm/test", {
        method: "POST",
        body: { profile }
      });
      this.setNotice(`LLM test passed in ${result.latency_ms ?? 0}ms.`);
      return result;
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
    async aiFillTemplate(payload) {
      const result = await api("/api/prompt-templates/ai-fill", { method: "POST", body: payload });
      this.setNotice("AI fill completed.");
      return result;
    },
    async saveSkillBundle(bundle) {
      const id = itemId(bundle);
      const exists = this.skillBundles.some((item) => itemId(item) === id);
      const path = exists ? `/api/skills/bundles/${encodeURIComponent(id)}` : "/api/skills/bundles";
      const method = exists ? "PUT" : "POST";
      await api(path, { method, body: bundle });
      await this.loadConfig();
      this.setNotice(`Skill bundle ${id} saved.`);
    },
    async deleteSkillBundle(id) {
      await api(`/api/skills/bundles/${encodeURIComponent(id)}`, { method: "DELETE" });
      await this.loadConfig();
      this.setNotice(`Skill bundle ${id} deleted.`);
    },
    async listSkills(bundleId) {
      return api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills`);
    },
    async readSkill(bundleId, skillName) {
      return api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}`);
    },
    async saveSkill(bundleId, skillName, payload) {
      const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}`, {
        method: "PUT",
        body: payload
      });
      this.setNotice(`Skill ${skillName} saved.`);
      return result;
    },
    async createSkill(bundleId, payload) {
      const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills`, {
        method: "POST",
        body: payload
      });
      this.setNotice(`Skill ${payload.name || payload.id} created.`);
      return result;
    },
    async deleteSkill(bundleId, skillName) {
      const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}`, {
        method: "DELETE"
      });
      this.setNotice(`Skill ${skillName} archived.`);
      return result;
    },
    async readSupportFile(bundleId, skillName, filePath) {
      return api(
        `/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}/files/${encodeURIComponent(filePath)}`
      );
    },
    async saveSupportFile(bundleId, skillName, filePath, content) {
      const result = await api(`/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}/files`, {
        method: "POST",
        body: { file_path: filePath, content }
      });
      this.setNotice(`Support file ${filePath} saved.`);
      return result;
    },
    async uploadSupportFile(bundleId, skillName, filePath, contentBase64) {
      const result = await api(
        `/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}/files/upload`,
        {
          method: "POST",
          body: { file_path: filePath, content_base64: contentBase64 }
        }
      );
      this.setNotice(`Support file ${filePath} uploaded.`);
      return result;
    },
    async deleteSupportFile(bundleId, skillName, filePath) {
      const result = await api(
        `/api/skills/bundles/${encodeURIComponent(bundleId)}/skills/${encodeURIComponent(skillName)}/files/${encodeURIComponent(filePath)}`,
        { method: "DELETE" }
      );
      this.setNotice(`Support file ${filePath} deleted.`);
      return result;
    },
    async loadDashboard() {
      this.dashboard = await api("/api/dashboard");
    },
    async loadImages() {
      this.images = await api("/api/docker/images");
    },
    async imageAction(action, extra = {}) {
      const result = await api("/api/docker/images/action", {
        method: "POST",
        body: { action, ...extra }
      });
      this.setNotice(`Image action ${action} completed.`);
      await this.loadImages();
      return result;
    },
    async loadResources() {
      this.resources = await api("/api/docker/resources");
    },
    async resourceAction(action, resource, extra = {}) {
      const result = await api("/api/docker/resources/action", {
        method: "POST",
        body: {
          action,
          kind: resource.kind,
          name: resource.name,
          ...extra
        }
      });
      this.setNotice(`Resource action ${action} completed.`);
      await this.loadResources();
      return result;
    },
    async exportConfig(includeSecrets = false) {
      const result = await api("/api/export", { method: "POST", body: { include_secrets: includeSecrets } });
      this.setNotice("Generated export written.");
      return result;
    }
  }
});
