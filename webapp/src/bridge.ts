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
  shareMaxContent?: (params: { text?: string; link?: string }) => Promise<unknown>;
  HapticFeedback?: { notificationOccurred?: (type: 'error' | 'success' | 'warning') => void };
}

declare global {
  interface Window {
    WebApp?: WebApp;
  }
}

export const webApp: WebApp | undefined = window.WebApp;
export const initData: string = webApp?.initData ?? '';

// Запасной вход по ссылке из бота: /app/?start=...#login=<токен>.
// Токен убираем из адресной строки и держим в sessionStorage на время вкладки.
function readLoginToken(): string {
  const match = /(?:^|&)login=([^&]+)/.exec(window.location.hash.slice(1));
  if (match) {
    const token = decodeURIComponent(match[1]);
    try {
      sessionStorage.setItem('login-token', token);
    } catch {
      /* без sessionStorage токен живёт до перезагрузки */
    }
    history.replaceState(null, '', window.location.pathname + window.location.search);
    return token;
  }
  try {
    return sessionStorage.getItem('login-token') ?? '';
  } catch {
    return '';
  }
}

export const loginToken: string = initData ? '' : readLoginToken();
export const isAuthorized = Boolean(initData || loginToken);
export const startParam: string =
  webApp?.initDataUnsafe?.start_param || new URLSearchParams(window.location.search).get('start') || '';

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

/** Экран «Поделиться» внутри MAX доступен, только когда приложение открыто из клиента MAX. */
export const canShareToMax = Boolean(initData && typeof webApp?.shareMaxContent === 'function');

/** Открывает выбор чата MAX для пересылки текста со ссылкой. false — если не получилось. */
export async function shareToMax(text: string, link: string): Promise<boolean> {
  if (!canShareToMax) return false;
  try {
    await webApp!.shareMaxContent!({ text, link });
    return true;
  } catch {
    return false;
  }
}

/** Лёгкий тактильный отклик; на десктопе и в вебе молча ничего не делает. */
export function haptic(type: 'error' | 'success' | 'warning'): void {
  try {
    webApp?.HapticFeedback?.notificationOccurred?.(type);
  } catch {
    /* не поддерживается */
  }
}
