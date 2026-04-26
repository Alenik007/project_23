import type { GenerateRequest } from "./types";

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getApiUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!url) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  return url.replace(/\/$/, "");
}

export async function generateText(
  prompt: string,
  options?: Pick<GenerateRequest, "max_tokens" | "temperature">,
): Promise<{ result: string; max_tokens: number; temperature: number }> {
  const res = await fetch(`${getApiUrl()}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      max_tokens: options?.max_tokens ?? 256,
      temperature: options?.temperature ?? 0.7,
    }),
  });

  if (res.status === 429) {
    throw new ApiError("Rate limit exceeded. Please wait and try again.", 429);
  }
  if (res.status === 422) {
    throw new ApiError("Invalid input. Check prompt length and parameters.", 422);
  }
  if (res.status === 400) {
    throw new ApiError("Prompt rejected by security filter.", 400);
  }
  if (res.status >= 500) {
    throw new ApiError("Server error. Please try again later.", res.status);
  }
  if (!res.ok) {
    throw new ApiError(`Request failed (${res.status})`, res.status);
  }
  return res.json() as Promise<{ result: string; max_tokens: number; temperature: number }>;
}

async function parseErrorBody(res: Response): Promise<string | undefined> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
    }
  } catch {
    /* ignore */
  }
  return undefined;
}

/**
 * POST /generate/stream — читает ReadableStream, декодирует UTF-8, вызывает onToken для каждого чанка.
 */
export async function streamGenerateText(
  prompt: string,
  options?: {
    max_tokens?: number;
    temperature?: number;
    signal?: AbortSignal;
    onToken?: (chunk: string) => void;
  },
): Promise<void> {
  const res = await fetch(`${getApiUrl()}/generate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      max_tokens: options?.max_tokens ?? 256,
      temperature: options?.temperature ?? 0.7,
    }),
    signal: options?.signal,
  });

  if (res.status === 429) {
    throw new ApiError("Rate limit exceeded. Please wait and try again.", 429);
  }
  if (res.status === 422) {
    const extra = await parseErrorBody(res);
    throw new ApiError(extra ?? "Invalid input. Check prompt length and parameters.", 422);
  }
  if (res.status === 400) {
    const extra = await parseErrorBody(res);
    throw new ApiError(extra ?? "Prompt rejected by security filter.", 400);
  }
  if (res.status >= 500) {
    throw new ApiError("Server error. Please try again later.", res.status);
  }
  if (!res.ok) {
    throw new ApiError(`Request failed (${res.status})`, res.status);
  }

  const body = res.body;
  if (!body) {
    throw new ApiError("Empty response body from server");
  }

  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value && value.byteLength > 0) {
      const chunk = decoder.decode(value, { stream: true });
      if (chunk && options?.onToken) options.onToken(chunk);
    }
  }
  const tail = decoder.decode();
  if (tail && options?.onToken) options.onToken(tail);
}
