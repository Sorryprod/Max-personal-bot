import { Button } from '@maxhub/max-ui';
import { Bookmark, Check, Phone, TriangleAlert, Undo2, X } from 'lucide-react';
import { formatPhone } from '../format';
import { STATUS_LABELS, STATUS_TONES } from '../statuses';
import type { Application, ApplicationStatus, Question } from '../types';
import { ConfirmButton } from './ConfirmButton';
import { Avatar, ICON, Tag } from './ui';

interface Props {
  app: Application;
  questions: Question[];
  busy: boolean;
  onStatus: (status: ApplicationStatus) => void;
}

export function formatDate(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
}

export function CandidateCard({ app, questions, busy, onStatus }: Props) {
  const answers = new Map(app.answers.map((a) => [a.question_id, a]));
  const pending = app.status === 'screened' || app.status === 'invited';

  return (
    <article className="card">
      <div className="candidate__head">
        <div className="person">
          <Avatar name={app.name} />
          <div className="person__body">
            <h3 className="h3">{app.name}</h3>
            <a className="phone" href={`tel:${app.contact}`}>
              <Phone size={14} strokeWidth={2} />
              {formatPhone(app.contact)}
            </a>
          </div>
        </div>
        <Tag tone={STATUS_TONES[app.status]}>{STATUS_LABELS[app.status]}</Tag>
      </div>

      {app.screening_failed && (
        <Tag tone="danger">
          <TriangleAlert size={13} strokeWidth={2.2} />
          Не прошёл отсеивающие вопросы
        </Tag>
      )}

      {questions.length > 0 && (
        <dl className="answers">
          {questions.map((q) => {
            const a = answers.get(q.id);
            const bad = a && !a.passed;
            return [
              <dt key={`q${q.id}`}>{q.text}</dt>,
              <dd key={`a${q.id}`} className={bad ? 'bad' : q.is_blocking ? 'ok' : ''}>
                {q.is_blocking && a && (bad ? <X size={14} strokeWidth={2.4} /> : <Check size={14} strokeWidth={2.4} />)}
                {a ? a.display : '—'}
              </dd>,
            ];
          })}
        </dl>
      )}
      <span className="small faint">Отклик {formatDate(app.created_at)}</span>

      <div className="actions">
        {pending ? (
          <>
            {app.status === 'screened' && (
              <Button size="medium" variant="secondary" disabled={busy} iconBefore={<Bookmark {...ICON} />}
                onClick={() => onStatus('reserve')}>
                В резерв
              </Button>
            )}
            <ConfirmButton size="medium" variant="secondary" disabled={busy} confirmText="Точно отказать?"
              onClick={() => onStatus('rejected')}>
              Отказать
            </ConfirmButton>
          </>
        ) : (
          <Button size="medium" variant="secondary" disabled={busy} iconBefore={<Undo2 {...ICON} />}
            onClick={() => onStatus('screened')}>
            Вернуть к рассмотрению
          </Button>
        )}
      </div>
    </article>
  );
}
