// Минимальные типы MAX Bridge (https://dev.max.ru/docs/webapps/bridge)
export interface WebAppUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
}

export interface WebApp {
  initData: string;
  initDataUnsafe: { user?: WebAppUser; start_param?: string; auth_date?: number };
  platform?: string;
  ready?: () => void;
  close?: () => void;
}

declare global {
  interface Window {
    WebApp?: WebApp;
  }
}

export const webApp: WebApp | undefined = window.WebApp;
export const initData: string = webApp?.initData ?? '';
