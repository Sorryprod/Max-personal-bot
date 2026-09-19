import type { ReactNode } from 'react';
import { Button } from '@maxhub/max-ui';
import { CircleAlert, CloudOff, LoaderCircle, type LucideIcon } from 'lucide-react';
import { ICON, IconCircle } from './ui';

export function Loading({ text = 'Загружаем…' }: { text?: string }) {
  return (
    <div className="state" role="status">
      <LoaderCircle className="spinner" size={28} strokeWidth={2} aria-hidden />
      <p className="text muted">{text}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state" role="alert">
      <IconCircle icon={CloudOff} tone="danger" />
      <h2 className="h2">Не получилось загрузить</h2>
      <p className="text muted">{message}</p>
      {onRetry && (
        <div className="state__actions">
          <Button variant="secondary" onClick={onRetry}>Попробовать ещё раз</Button>
        </div>
      )}
    </div>
  );
}

interface EmptyProps {
  icon: LucideIcon;
  title: string;
  hint: string;
  actions?: ReactNode;
}

export function EmptyState({ icon, title, hint, actions }: EmptyProps) {
  return (
    <div className="state">
      <IconCircle icon={icon} />
      <h2 className="h2">{title}</h2>
      <p className="text muted">{hint}</p>
      {actions && <div className="state__actions">{actions}</div>}
    </div>
  );
}

export function Banner({ kind = 'error', children }: { kind?: 'error' | 'info'; children: ReactNode }) {
  return (
    <div className={`banner banner--${kind}`} role={kind === 'error' ? 'alert' : undefined}>
      <CircleAlert {...ICON} />
      <span>{children}</span>
    </div>
  );
}
