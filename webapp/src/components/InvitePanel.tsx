import { useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { Plus, Send, X } from 'lucide-react';
import type { ApiError } from '../api';
import { Banner } from './States';
import { ICON } from './ui';

const MIN_SLOTS = 2;
const MAX_SLOTS = 3;

interface SlotDraft {
  date: string; // YYYY-MM-DD
  time: string; // HH:MM
}

const pad = (n: number) => String(n).padStart(2, '0');
const isoDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** Ближайшие рабочие дни, начиная с завтра. */
function nextWorkdays(count: number): string[] {
  const days: string[] = [];
  const d = new Date();
  while (days.length < count) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0) days.push(isoDate(d));
  }
  return days;
}

function defaultSlots(): SlotDraft[] {
  const [first, second] = nextWorkdays(2);
  return [
    { date: first!, time: '11:00' },
    { date: first!, time: '15:00' },
    { date: second!, time: '11:00' },
  ];
}

interface Props {
  onSubmit: (slots: string[]) => Promise<void>;
  onCancel: () => void;
}

export function InvitePanel({ onSubmit, onCancel }: Props) {
  const [slots, setSlots] = useState<SlotDraft[]>(defaultSlots);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const today = isoDate(new Date());

  const update = (i: number, patch: Partial<SlotDraft>) =>
    setSlots((s) => s.map((slot, j) => (j === i ? { ...slot, ...patch } : slot)));

  const submit = async () => {
    const values = slots.map((s) => `${s.date}T${s.time}`);
    if (slots.some((s) => !s.date || !s.time)) return setError('Укажите дату и время у каждого варианта');
    if (new Set(values).size !== values.length) return setError('Варианты времени не должны повторяться');
    setError(null);
    setSending(true);
    try {
      await onSubmit(values);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="invite">
      <div className="stack-s">
        <span className="h3">Приглашение на собеседование</span>
        <span className="small muted">Кандидат выберет удобное время кнопкой в чате, адрес подставится из вакансии.</span>
      </div>
      {slots.map((slot, i) => (
        <div key={i} className="invite__row">
          <input type="date" className="native-field" value={slot.date} min={today} aria-label={`Дата, вариант ${i + 1}`}
            onChange={(e) => update(i, { date: e.target.value })} />
          <input type="time" className="native-field" value={slot.time} step={900} aria-label={`Время, вариант ${i + 1}`}
            onChange={(e) => update(i, { time: e.target.value })} />
          {slots.length > MIN_SLOTS && (
            <button type="button" className="icon-button" aria-label="Убрать вариант"
              onClick={() => setSlots((s) => s.filter((_, j) => j !== i))}>
              <X {...ICON} />
            </button>
          )}
        </div>
      ))}
      {slots.length < MAX_SLOTS && (
        <button type="button" className="add-link"
          onClick={() => setSlots((s) => [...s, { date: s[s.length - 1]?.date ?? today, time: '17:00' }])}>
          <Plus {...ICON} />
          Ещё вариант
        </button>
      )}
      {error && <Banner>{error}</Banner>}
      <div className="actions">
        <Button variant="secondary" disabled={sending} onClick={onCancel}>Отмена</Button>
        <Button loading={sending} disabled={sending} iconBefore={<Send {...ICON} />} onClick={submit}>
          Отправить
        </Button>
      </div>
    </div>
  );
}
