// Минимальные типы MAX Bridge (https://dev.max.ru/docs/webapps/bridge).
// Все вызовы защищены: вне MAX или в старой версии клиента метода может не быть.
export interface WebAppUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
}

interface BackButton {
  show?: () => void;
  hide?: () => void;
  onClick?: (cb: () => void) => void;
  offClick?: (cb: () => void) => void;
}

export interface WebApp {
  initData: string;
  initDataUnsafe: { user?: WebAppUser; start_param?: string; auth_date?: number };
  platform?: string;
  ready?: () => void;
  close?: () => void;
  BackButton?: BackButton;
}

declare global {
  interface Window {
    WebApp?: WebApp;
  }
}

export const webApp: WebApp | undefined = window.WebApp;
export const initData: string = webApp?.initData ?? '';
export const startParam: string = webApp?.initDataUnsafe?.start_param ?? '';

export function closeApp(): void {
  try {
    webApp?.close?.();
  } catch {
    /* вне MAX закрывать нечего */
  }
}

/** Системная кнопка «Назад» MAX; возвращает функцию отписки. */
export function bindBackButton(handler: (() => void) | null): () => void {
  const back = webApp?.BackButton;
  if (!back) return () => {};
  try {
    if (!handler) {
      back.hide?.();
      return () => {};
    }
    back.onClick?.(handler);
    back.show?.();
  } catch {
    return () => {};
  }
  return () => {
    try {
      back.offClick?.(handler);
    } catch {
      /* ignore */
    }
  };
}
