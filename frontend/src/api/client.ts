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
      credentials: "include",
      headers: {
        Accept: "application/json",
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
  if (!response.ok)
    throw new ApiError(
      response.status === 401 ? "unauthorized" : "requestFailed",
    );
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("requestFailed");
  }
}
