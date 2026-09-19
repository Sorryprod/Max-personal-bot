import { initData, loginToken } from './bridge';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`/api${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(initData ? { 'X-Init-Data': initData } : { 'X-Login-Token': loginToken }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError('Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.', 0, 'network');
  }
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    const detail = data?.detail;
    const message =
      typeof detail?.message === 'string' ? detail.message : 'Что-то пошло не так. Попробуйте ещё раз.';
    throw new ApiError(message, resp.status, detail?.code ?? 'unknown');
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
};
