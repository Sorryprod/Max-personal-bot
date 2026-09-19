import { useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { Bookmark, CalendarCheck, CalendarClock, Check, Phone, TriangleAlert, Undo2, X } from 'lucide-react';
import { formatPhone, formatSlot } from '../format';
import { STATUS_LABELS, STATUS_TONES } from '../statuses';
import type { Application, ApplicationStatus, Question } from '../types';
import { ConfirmButton } from './ConfirmButton';
import { InvitePanel } from './InvitePanel';
import { Avatar, ICON, Tag } from './ui';

interface Props {
  app: Application;
  questions: Question[];
  timezone: string;
  busy: boolean;
  onStatus: (status: ApplicationStatus) => void;
  onInvite: (slots: string[]) => Promise<void>;
}

export function formatDate(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
}

export function CandidateCard({ app, questions, timezone, busy, onStatus, onInvite }: Props) {
  const [inviting, setInviting] = useState(false);
  const answers = new Map(app.answers.map((a) => [a.question_id, a]));
  const chosen = app.slots.find((s) => s.is_chosen);

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

      {app.status === 'invited' && app.slots.length > 0 && (
        <div className="interview">
          {chosen ? (
            <>
              <CalendarCheck {...ICON} />
              <div className="stack-s">
                <span className="small muted">Собеседование</span>
                <b>{formatSlot(chosen.starts_at, timezone)}</b>
              </div>
            </>
          ) : (
            <>
              <CalendarClock {...ICON} />
              <div className="stack-s">
                <span className="small muted">Ждём, когда кандидат выберет время</span>
                <span className="small">{app.slots.map((s) => formatSlot(s.starts_at, timezone)).join(' · ')}</span>
              </div>
            </>
          )}
        </div>
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

      {inviting ? (
        <InvitePanel
          onCancel={() => setInviting(false)}
          onSubmit={async (slots) => {
            await onInvite(slots);
            setInviting(false);
          }}
        />
      ) : (
        <div className="actions">
          {(app.status === 'screened' || app.status === 'reserve') && (
            <Button disabled={busy} iconBefore={<CalendarClock {...ICON} />} onClick={() => setInviting(true)}>
              Пригласить
            </Button>
          )}
          {app.status === 'invited' && (
            <Button variant="secondary" disabled={busy} iconBefore={<CalendarClock {...ICON} />}
              onClick={() => setInviting(true)}>
              {chosen ? 'Перенести' : 'Другое время'}
            </Button>
          )}
          {app.status === 'screened' && (
            <Button variant="secondary" disabled={busy} iconBefore={<Bookmark {...ICON} />} onClick={() => onStatus('reserve')}>
              В резерв
            </Button>
          )}
          {app.status !== 'rejected' && (
            <ConfirmButton variant="secondary" disabled={busy} confirmText="Точно отказать?" onClick={() => onStatus('rejected')}>
              Отказать
            </ConfirmButton>
          )}
          {(app.status === 'reserve' || app.status === 'rejected') && (
            <Button variant="secondary" disabled={busy} iconBefore={<Undo2 {...ICON} />} onClick={() => onStatus('screened')}>
              Вернуть
            </Button>
          )}
        </div>
      )}
    </article>
  );
}
