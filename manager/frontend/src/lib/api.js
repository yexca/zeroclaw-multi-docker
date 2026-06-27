export class ApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "ApiError";
    this.details = details;
  }
}

export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options,
    body: options.body && typeof options.body !== "string" ? JSON.stringify(options.body) : options.body
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    const error = payload.error || {};
    throw new ApiError(error.message || response.statusText || "Request failed", error.details || {});
  }
  return payload.data ?? payload;
}

export function itemId(item) {
  return item?.id || item?.alias || item?.server_name || "";
}

export function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null));
}

export function compactJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}
