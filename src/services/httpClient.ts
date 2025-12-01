// src/services/httpClient.ts

export const BASE_URL = 'http://localhost:8000';

/**
 * Build a URL with optional query params.
 */
function buildUrl(
  path: string,
  params?: Record<string, string | number | boolean | undefined>
): string {
  const url = new URL(path, BASE_URL);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  return url.toString();
}

/**
 * Generic GET helper that wraps fetch and parses JSON.
 */
type RequestOptions = {
  headers?: Record<string, string>;
};

function mergeHeaders(base: Record<string, string>, extra?: Record<string, string>): Record<string, string> {
  if (!extra) {
    return base;
  }
  return { ...base, ...extra };
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(path, params);

  const res = await fetch(url, {
    method: 'GET',
    headers: mergeHeaders(
      {
        Accept: 'application/json',
      },
      options?.headers
    ),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `GET ${url} failed with status ${res.status} ${res.statusText} ${text ? `- ${text}` : ''}`.trim()
    );
  }

  return (await res.json()) as T;
}

/**
 * Centralized API error logger.
 */
export function logApiError(source: string, error: unknown): void {
  // eslint-disable-next-line no-console
  console.error(`[API ERROR] ${source}`, error);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(path);
  const res = await fetch(url, {
    method: 'POST',
    headers: mergeHeaders(
      {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      options?.headers
    ),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `POST ${url} failed with status ${res.status} ${res.statusText} ${text ? `- ${text}` : ''}`.trim()
    );
  }

  if (res.status === 204) {
    return {} as T;
  }

  return (await res.json()) as T;
}
