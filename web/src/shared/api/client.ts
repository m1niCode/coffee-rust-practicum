/** Ошибка API с понятным текстом для пользователя. */
export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch('/api' + path, init);
  } catch {
    throw new ApiError('Нет связи с программой. Проверьте, что она запущена (python app.py).');
  }
  if (!res.ok) {
    let msg = `Ошибка ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') msg = body.detail;
      else if (Array.isArray(body.detail)) msg = 'Проверьте значения параметров.';
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(msg);
  }
  return (await res.json()) as T;
}

export const post = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
