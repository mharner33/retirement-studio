async function request<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} failed: ${String(res.status)}`);
  return (await res.json()) as T;
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(path, "GET");
}

export function putJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, "PUT", body);
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, "POST", body);
}
