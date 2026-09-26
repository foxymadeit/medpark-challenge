export class ApiError extends Error {
  code: string;
  constructor(code: string) {
    super(code);
    this.code = code;
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        // Marks writes as the app's own; the server's Origin check is what
        // refuses writes from pages on other sites.
        ...(options.method && options.method !== "GET"
          ? { "X-Requested-With": "Liminal" }
          : {}),
        ...(options.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
      signal: options.signal ?? AbortSignal.timeout(20000),
    });
  } catch {
    throw new ApiError("offline");
  }
  if (!response.ok) throw new ApiError("requestFailed");
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("requestFailed");
  }
}
