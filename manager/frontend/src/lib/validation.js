const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$/;
const SKILL_BUNDLE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
const SIMPLE_NAME_PATTERN = /^[A-Za-z0-9_.-]+$/;
const SUPPORT_PATH_PATTERN = /^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/;

export function addError(errors, key, message) {
  if (!message) return;
  errors[key] = message;
}

export function isHttpUrl(value) {
  if (!String(value || "").trim()) return true;
  try {
    const url = new URL(String(value).trim());
    return ["http:", "https:"].includes(url.protocol) && Boolean(url.hostname);
  } catch (_error) {
    return false;
  }
}

export function validateRequired(errors, key, value, message) {
  if (!String(value ?? "").trim()) addError(errors, key, message);
}

export function validateId(errors, key, value, message) {
  if (!ID_PATTERN.test(String(value || ""))) addError(errors, key, message);
}

export function validateSkillBundleId(errors, key, value, message) {
  if (!SKILL_BUNDLE_ID_PATTERN.test(String(value || ""))) addError(errors, key, message);
}

export function validateHttpUrl(errors, key, value, message) {
  if (!isHttpUrl(value)) addError(errors, key, message);
}

export function validateIntegerRange(errors, key, value, { min, max, message }) {
  if (value === "" || value === null || value === undefined) return;
  if (!Number.isInteger(Number(value))) {
    addError(errors, key, message);
    return;
  }
  const number = Number(value);
  if ((min !== undefined && number < min) || (max !== undefined && number > max)) {
    addError(errors, key, message);
  }
}

export function parseJsonText(errors, key, value, fallback, message) {
  try {
    return JSON.parse(value || "null") ?? fallback;
  } catch (_error) {
    addError(errors, key, message);
    return fallback;
  }
}

export function validatePromptFileName(errors, key, value, message) {
  const filename = String(value || "").trim().replaceAll("\\", "/").split("/").pop();
  if (!filename || !SIMPLE_NAME_PATTERN.test(filename)) {
    addError(errors, key, message);
    return "";
  }
  return filename;
}

export function validateSupportPath(errors, key, value, allowedPrefix, message) {
  const path = String(value || "").trim().replaceAll("\\", "/");
  if (!path || path.includes("..") || path.startsWith("/") || !SUPPORT_PATH_PATTERN.test(path)) {
    addError(errors, key, message);
    return "";
  }
  if (allowedPrefix && !path.startsWith(`${allowedPrefix}/`)) {
    addError(errors, key, message);
    return "";
  }
  return path;
}

export function validateRelativeDirectory(errors, key, value, message) {
  const path = String(value || "").trim().replaceAll("\\", "/");
  if (!path || path.includes("..") || path.startsWith("/") || !SUPPORT_PATH_PATTERN.test(path)) {
    addError(errors, key, message);
  }
}

export function firstError(errors) {
  return Object.values(errors).find(Boolean) || "";
}

export function valueExists(rows, value, currentValue = "") {
  const normalized = String(value || "");
  if (!normalized) return false;
  return rows.some((row) => String(row?.id || row?.alias || row?.server_name || "") === normalized && normalized !== String(currentValue || ""));
}
