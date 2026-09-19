import { Button, Typography } from '@maxhub/max-ui';
import { STATUS_LABELS } from '../statuses';
import type { Application, ApplicationStatus, Question } from '../types';
import { ConfirmButton } from './ConfirmButton';

interface Props {
  app: Application;
  questions: Question[];
  busy: boolean;
  onStatus: (status: ApplicationStatus) => void;
}

export function formatDate(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function CandidateCard({ app, questions, busy, onStatus }: Props) {
  const answers = new Map(app.answers.map((a) => [a.question_id, a]));
  return (
    <div className={`card candidate ${app.screening_failed ? 'candidate--failed' : ''}`}>
      <div className="candidate__head">
        <div>
          <Typography.Headline>{app.name}</Typography.Headline>
          <a className="phone" href={`tel:${app.contact}`}>{app.contact}</a>
        </div>
        <span className={`badge badge--${app.status}`}>{STATUS_LABELS[app.status]}</span>
      </div>
      {app.screening_failed && <div className="warn">⚠️ Не прошёл отсеивающие вопросы</div>}

      <ul className="answers">
        {questions.map((q) => {
          const a = answers.get(q.id);
          return (
            <li key={q.id} className={a && !a.passed ? 'answer--bad' : ''}>
              <span className="muted">{q.text}</span>
              <b>{a ? `${q.is_blocking ? (a.passed ? '✓ ' : '✗ ') : ''}${a.display}` : '—'}</b>
            </li>
          );
        })}
      </ul>
      <span className="muted small">Откликнулся {formatDate(app.created_at)}</span>

      <div className="actions">
        {app.status === 'screened' || app.status === 'invited' ? (
          <>
            {app.status === 'screened' && (
              <Button size="small" variant="secondary" disabled={busy} onClick={() => onStatus('reserve')}>
                В резерв
              </Button>
            )}
            <ConfirmButton size="small" variant="secondary" disabled={busy} confirmText="Точно отказать?"
              onClick={() => onStatus('rejected')}>
              Отказать
            </ConfirmButton>
          </>
        ) : (
          <Button size="small" variant="secondary" disabled={busy} onClick={() => onStatus('screened')}>
            Вернуть к рассмотрению
          </Button>
        )}
      </div>
    </div>
  );
}
