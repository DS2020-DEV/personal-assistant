const readError = async (res: Response) => {
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.error === "string") return data.error;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((item: { msg?: string }) => item.msg || JSON.stringify(item)).join(" ");
    }
  } catch {
    /* plain text */
  }
  return text || res.statusText;
};

const explainNetwork = (err: unknown) => {
  const name = err instanceof Error ? err.name : "";
  const msg = err instanceof Error ? err.message : String(err);
  if (name === "AbortError") {
    return "The dashboard did not answer in time. Refresh http://127.0.0.1:8787.";
  }
  if (/failed to fetch/i.test(msg)) {
    return "Could not reach the API. Use http://127.0.0.1:8787 (not another port).";
  }
  return msg.replace(/^Error:\s*/, "");
};

const request = async (path: string, init: RequestInit = {}, timeoutMs = 0) => {
  const ctrl = timeoutMs > 0 ? new AbortController() : undefined;
  const timer = timeoutMs > 0 ? window.setTimeout(() => ctrl?.abort(), timeoutMs) : 0;
  try {
    const res = await fetch(path, { ...init, signal: ctrl?.signal });
    if (!res.ok) {
      throw new Error(await readError(res));
    }
    return res.json();
  } catch (err) {
    throw new Error(explainNetwork(err));
  } finally {
    if (timer) window.clearTimeout(timer);
  }
};

export const api = {
  get: (path: string) => request(path),
  post: (path: string, body?: unknown) =>
    request(
      path,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : "{}",
      },
      120000,
    ),
  put: (path: string, body?: unknown) =>
    request(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  patch: (path: string, body?: unknown) =>
    request(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  delete: (path: string) => request(path, { method: "DELETE" }),
};
