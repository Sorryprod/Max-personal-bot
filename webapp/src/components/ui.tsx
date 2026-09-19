import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { ChevronLeft } from 'lucide-react';

export const ICON = { size: 18, strokeWidth: 1.9 } as const;

export function IconCircle({ icon: Icon, tone = 'brand' }: { icon: LucideIcon; tone?: 'brand' | 'danger' | 'accent' }) {
  return (
    <span className={`icon-circle ${tone !== 'brand' ? `icon-circle--${tone}` : ''}`}>
      <Icon size={26} strokeWidth={1.8} />
    </span>
  );
}

export function Meta({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <span className="meta__item">
      <Icon {...ICON} size={16} />
      {children}
    </span>
  );
}

export function Tag({ tone, children }: { tone?: 'brand' | 'accent' | 'danger'; children: ReactNode }) {
  return <span className={`tag ${tone ? `tag--${tone}` : ''}`}>{children}</span>;
}

export function TopBar({ onBack, backLabel = 'Назад' }: { onBack: () => void; backLabel?: string }) {
  return (
    <div className="topbar">
      <button type="button" className="icon-button" onClick={onBack}>
        <ChevronLeft size={22} strokeWidth={2} />
        {backLabel}
      </button>
    </div>
  );
}

const AVATAR_TONES = 5;

export function Avatar({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join('');
  // Цвет стабилен для имени: одинаковый человек — одинаковый аватар в карточках и таблице.
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return (
    <span className={`avatar avatar--${hash % AVATAR_TONES}`} aria-hidden>
      {initials || '?'}
    </span>
  );
}
