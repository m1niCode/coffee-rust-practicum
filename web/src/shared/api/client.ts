/** Ошибка API с понятным текстом для пользователя. */
export class ApiError extends Error {
  constructor(message: string, readonly status = 0) {
    super(message);
  }
}

let onUnauthorized: (() => void) | null = null;
/** Слой выше (entities/session) сообщает, что делать, когда сервер просит войти. */
export const setUnauthorizedHandler = (fn: () => void): void => { onUnauthorized = fn; };

/** Адреса относительные: приложение работает под любым префиксом (например /kofi/). */
export const apiUrl = (path: string): string => 'api' + path;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), { credentials: 'same-origin', ...init });
  } catch {
    throw new ApiError('Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.');
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
    if (res.status === 401) onUnauthorized?.();
    if (res.status === 413) msg = msg.startsWith('Ошибка') ? 'Слишком большая загрузка. Разбейте её на части.' : msg;
    throw new ApiError(msg, res.status);
  }
  return (await res.json()) as T;
}

export const post = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

/** Загрузка файлов с индикатором (fetch не умеет показывать ход отправки, поэтому XMLHttpRequest). */
export function upload<T>(path: string, form: FormData, onProgress?: (share: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', apiUrl(path));
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(e.loaded / e.total); };
    xhr.onerror = () => reject(new ApiError('Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.'));
    xhr.onload = () => {
      let body: { detail?: unknown } = {};
      try { body = JSON.parse(xhr.responseText) as { detail?: unknown }; } catch { /* не JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body as T);
      if (xhr.status === 401) onUnauthorized?.();
      const msg = typeof body.detail === 'string' ? body.detail
        : xhr.status === 413 ? 'Слишком большая загрузка. Разбейте её на части.' : `Ошибка ${xhr.status}`;
      reject(new ApiError(msg, xhr.status));
    };
    xhr.send(form);
  });
}
