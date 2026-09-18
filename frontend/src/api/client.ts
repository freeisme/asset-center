export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function readCookie(name: string): string {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) return decodeURIComponent(value.slice(prefix.length));
  }
  return "";
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  csrf?: boolean;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  const hasBody = options.body !== undefined;
  if (hasBody) headers["Content-Type"] = "application/json";
  const safeMethod = ["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
  if (!safeMethod && options.csrf !== false) {
    const token = readCookie("oa_csrf");
    if (token) headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: hasBody ? JSON.stringify(options.body) : undefined,
  });
  const raw = await response.text();
  let payload: Record<string, unknown> = {};
  if (raw) {
    try {
      payload = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      payload = {};
    }
  }
  if (!response.ok) {
    throw new ApiError(
      String(payload.error ?? `请求失败（HTTP ${response.status}）`),
      response.status,
      String(payload.code ?? ""),
    );
  }
  return payload as T;
}
