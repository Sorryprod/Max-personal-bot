import type { ReactNode } from 'react';
import { Button, Spinner, Typography } from '@maxhub/max-ui';

export function Loading({ text = 'Загрузка…' }: { text?: string }) {
  return (
    <div className="state">
      <Spinner size={24} />
      <Typography.Body>{text}</Typography.Body>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state">
      <div className="state__icon">⚠️</div>
      <Typography.Body>{message}</Typography.Body>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Повторить
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, hint, action }: { icon: string; title: string; hint: string; action?: ReactNode }) {
  return (
    <div className="state">
      <div className="state__icon">{icon}</div>
      <Typography.Title>{title}</Typography.Title>
      <Typography.Body className="muted">{hint}</Typography.Body>
      {action}
    </div>
  );
}

export function Banner({ kind, children }: { kind: 'error' | 'success'; children: ReactNode }) {
  return <div className={`banner banner--${kind}`}>{children}</div>;
}
