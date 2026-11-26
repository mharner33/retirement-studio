export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(message);
  }
}

async function send(
  path: string,
  method: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<Response> {
  const res = await fetch(path, {
    method,
    headers:
      body === undefined || body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body: body === undefined || body instanceof FormData ? body : JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const payload = (await res.json().catch(() => undefined)) as { detail?: unknown } | undefined;
    throw new ApiError(
      `${method} ${path} failed: ${String(res.status)}`,
      res.status,
      payload?.detail,
    );
  }
  return res;
}

async function request<T>(
  path: string,
  method: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return (await (await send(path, method, body, signal)).json()) as T;
}

export async function getText(path: string, signal?: AbortSignal): Promise<string> {
  return (await send(path, "GET", undefined, signal)).text();
}

export function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, "GET", undefined, signal);
}

export function putJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, "PUT", body);
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, "POST", body);
}

export function postForm<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, "POST", form);
}

export async function deleteRequest(path: string): Promise<void> {
  await send(path, "DELETE");
}
