import type { ApplicationStatus } from './types';

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  screened: 'Ждёт решения',
  invited: 'Приглашён',
  reserve: 'В резерве',
  rejected: 'Отказ',
};

export const STATUS_TONES: Record<ApplicationStatus, 'brand' | 'accent' | 'danger' | undefined> = {
  screened: 'accent',
  invited: 'brand',
  reserve: undefined,
  rejected: 'danger',
};

export type Filter = ApplicationStatus | 'all';

export const FILTERS: { key: Filter; label: string }[] = [
  { key: 'screened', label: 'Ждут решения' },
  { key: 'invited', label: 'Приглашены' },
  { key: 'reserve', label: 'Резерв' },
  { key: 'rejected', label: 'Отказ' },
  { key: 'all', label: 'Все' },
];
