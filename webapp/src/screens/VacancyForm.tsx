import { useEffect, useState } from 'react';
import { Button, Input, Switch, Typography } from '@maxhub/max-ui';
import { api, ApiError } from '../api';
import { Banner } from '../components/States';
import { load, remove, save } from '../storage';
import type { Me, QuestionDraft, QuestionType, Vacancy, VacancyDraft } from '../types';

const DRAFT_KEY = 'vacancy-draft';
const POSITIONS = ['Повар', 'Продавец', 'Официант', 'Курьер', 'Уборщик', 'Бариста', 'Кассир'];
const SCHEDULES = ['2/2', '5/2', '3/3', 'Гибкий график'];
const TYPE_LABELS: Record<QuestionType, string> = { yes_no: 'Да / Нет', choice: 'Варианты', text: 'Свободный ответ' };

const EMPTY: VacancyDraft = { position: '', schedule: '', salary_from: '', salary_to: '', address: '', questions: [] };

type Errors = Partial<Record<keyof VacancyDraft | `q${number}`, string>>;

function validate(d: VacancyDraft): Errors {
  const e: Errors = {};
  const len = (s: string) => s.trim().length;
  if (len(d.position) < 2 || len(d.position) > 100) e.position = 'Укажите должность (2–100 символов)';
  if (len(d.schedule) < 2 || len(d.schedule) > 100) e.schedule = 'Укажите график (2–100 символов)';
  if (len(d.address) < 5 || len(d.address) > 200) e.address = 'Укажите адрес (5–200 символов)';
  const from = d.salary_from ? Number(d.salary_from) : null;
  const to = d.salary_to ? Number(d.salary_to) : null;
  for (const [key, v] of [['salary_from', from], ['salary_to', to]] as const) {
    if (v !== null && (!Number.isInteger(v) || v < 0 || v > 1_000_000)) e[key] = 'Число от 0 до 1 000 000';
  }
  if (from && to && from > to) e.salary_to = 'Меньше, чем «от»';
  d.questions.forEach((q, i) => {
    const options = q.options.map((o) => o.trim()).filter(Boolean);
    if (len(q.text) < 3) e[`q${i}`] = 'Текст вопроса — минимум 3 символа';
    else if (q.qtype === 'choice' && (options.length < 2 || new Set(options).size !== options.length))
      e[`q${i}`] = 'Нужно от 2 до 6 разных вариантов';
    else if (q.is_blocking && q.accepted.length === 0) e[`q${i}`] = 'Отметьте, какие ответы подходят';
    else if (q.is_blocking && q.accepted.length === (q.qtype === 'yes_no' ? 2 : options.length))
      e[`q${i}`] = 'Подходят все ответы — вопрос никого не отсеет';
  });
  return e;
}

function toPayload(d: VacancyDraft) {
  return {
    position: d.position.trim(),
    schedule: d.schedule.trim(),
    salary_from: d.salary_from ? Number(d.salary_from) : null,
    salary_to: d.salary_to ? Number(d.salary_to) : null,
    address: d.address.trim(),
    questions: d.questions.map((q) => ({
      ...q,
      options: q.qtype === 'choice' ? q.options.map((o) => o.trim()).filter(Boolean) : [],
    })),
  };
}

interface Props {
  me: Me;
  onCreated: (v: Vacancy) => void;
}

export function VacancyForm({ me, onCreated }: Props) {
  // Черновик переживает закрытие приложения — можно вернуться к введённым данным.
  const [draft, setDraft] = useState<VacancyDraft>(() => load<VacancyDraft>(DRAFT_KEY) ?? EMPTY);
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => save(DRAFT_KEY, draft), [draft]);

  const set = <K extends keyof VacancyDraft>(key: K, value: VacancyDraft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  const setQuestion = (i: number, patch: Partial<QuestionDraft>) =>
    set('questions', draft.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  const full = draft.questions.length >= me.max_questions;

  const submit = async () => {
    const found = validate(draft);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length) {
      setServerError('Проверьте отмеченные поля');
      return;
    }
    setSubmitting(true);
    try {
      const vacancy = await api.post<Vacancy>('/vacancies', toPayload(draft));
      remove(DRAFT_KEY);
      onCreated(vacancy);
    } catch (e) {
      setServerError((e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <Typography.Title>Новая вакансия</Typography.Title>

      <Field label="Должность" error={errors.position}>
        <Input value={draft.position} placeholder="Например, повар" onChange={(e) => set('position', e.target.value)} />
        <Chips items={POSITIONS} onPick={(v) => set('position', v)} />
      </Field>

      <Field label="График" error={errors.schedule}>
        <Input value={draft.schedule} placeholder="Например, 2/2 с 9 до 21" onChange={(e) => set('schedule', e.target.value)} />
        <Chips items={SCHEDULES} onPick={(v) => set('schedule', v)} />
      </Field>

      <div className="row">
        <Field label="Зарплата от, ₽" error={errors.salary_from}>
          <Input inputMode="numeric" value={draft.salary_from} placeholder="40000"
            onChange={(e) => set('salary_from', e.target.value.replace(/\D/g, ''))} />
        </Field>
        <Field label="до, ₽" error={errors.salary_to}>
          <Input inputMode="numeric" value={draft.salary_to} placeholder="60000"
            onChange={(e) => set('salary_to', e.target.value.replace(/\D/g, ''))} />
        </Field>
      </div>

      <Field label="Адрес" error={errors.address}>
        <Input value={draft.address} placeholder={`${me.employer?.city ?? 'Город'}, улица, дом`}
          onChange={(e) => set('address', e.target.value)} />
      </Field>

      <div className="section">
        <Typography.Headline>Отсеивающие вопросы</Typography.Headline>
        <Typography.Body className="muted">
          До {me.max_questions} вопросов. Кандидат ответит кнопками в чате, а вы сразу увидите, кто не подходит.
        </Typography.Body>

        {draft.questions.map((q, i) => (
          <QuestionEditor key={i} q={q} error={errors[`q${i}`]}
            onChange={(patch) => setQuestion(i, patch)}
            onRemove={() => set('questions', draft.questions.filter((_, j) => j !== i))} />
        ))}

        {!full && (
          <>
            <div className="chips">
              {me.question_templates
                .filter((t) => !draft.questions.some((q) => q.text === t.text))
                .map((t) => (
                  <button key={t.text} type="button" className="chip" onClick={() => set('questions', [...draft.questions, { ...t }])}>
                    + {t.text}
                  </button>
                ))}
            </div>
            <Button variant="secondary" stretched onClick={() =>
              set('questions', [...draft.questions, { text: '', qtype: 'yes_no', options: [], is_blocking: false, accepted: [] }])}>
              + Свой вопрос
            </Button>
          </>
        )}
      </div>

      {serverError && <Banner kind="error">{serverError}</Banner>}
      <Button stretched size="large" loading={submitting} disabled={submitting} onClick={submit}>
        Опубликовать
      </Button>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      {children}
      {error && <span className="field__error">{error}</span>}
    </label>
  );
}

function Chips({ items, onPick }: { items: string[]; onPick: (v: string) => void }) {
  return (
    <div className="chips">
      {items.map((item) => (
        <button key={item} type="button" className="chip" onClick={() => onPick(item)}>
          {item}
        </button>
      ))}
    </div>
  );
}

interface EditorProps {
  q: QuestionDraft;
  error?: string;
  onChange: (patch: Partial<QuestionDraft>) => void;
  onRemove: () => void;
}

function QuestionEditor({ q, error, onChange, onRemove }: EditorProps) {
  const answers = q.qtype === 'yes_no' ? [['yes', 'Да'], ['no', 'Нет']] : q.options.filter(Boolean).map((o) => [o, o]);
  const toggleAccepted = (value: string) =>
    onChange({ accepted: q.accepted.includes(value) ? q.accepted.filter((a) => a !== value) : [...q.accepted, value] });

  return (
    <div className="card">
      <div className="card__head">
        <Input value={q.text} placeholder="Текст вопроса" onChange={(e) => onChange({ text: e.target.value })} />
        <button type="button" className="icon-btn" aria-label="Удалить вопрос" onClick={onRemove}>✕</button>
      </div>

      <div className="segmented">
        {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => (
          <button key={t} type="button" className={`chip ${q.qtype === t ? 'chip--on' : ''}`}
            onClick={() => onChange({ qtype: t, accepted: [], is_blocking: t === 'text' ? false : q.is_blocking,
              options: t === 'choice' && q.options.length < 2 ? ['', ''] : q.options })}>
            {TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      {q.qtype === 'choice' && (
        <div className="options">
          {q.options.map((opt, i) => (
            <div key={i} className="card__head">
              <Input value={opt} placeholder={`Вариант ${i + 1}`}
                onChange={(e) => onChange({ options: q.options.map((o, j) => (j === i ? e.target.value : o)),
                  accepted: q.accepted.filter((a) => a !== opt) })} />
              {q.options.length > 2 && (
                <button type="button" className="icon-btn" aria-label="Удалить вариант"
                  onClick={() => onChange({ options: q.options.filter((_, j) => j !== i), accepted: q.accepted.filter((a) => a !== opt) })}>✕</button>
              )}
            </div>
          ))}
          {q.options.length < 6 && (
            <button type="button" className="chip" onClick={() => onChange({ options: [...q.options, ''] })}>+ Вариант</button>
          )}
        </div>
      )}

      {q.qtype !== 'text' && (
        <label className="switch-row">
          <span>Отсеивающий вопрос</span>
          <Switch checked={q.is_blocking}
            onChange={(e) => onChange({ is_blocking: e.target.checked, accepted: e.target.checked && q.qtype === 'yes_no' ? ['yes'] : [] })} />
        </label>
      )}

      {q.is_blocking && (
        <div>
          <Typography.Body className="muted">Какие ответы подходят:</Typography.Body>
          <div className="chips">
            {answers.map(([value, label]) => (
              <button key={value} type="button" className={`chip ${q.accepted.includes(value) ? 'chip--on' : ''}`}
                onClick={() => toggleAccepted(value)}>
                {q.accepted.includes(value) ? '✓ ' : ''}{label}
              </button>
            ))}
          </div>
        </div>
      )}
      {error && <span className="field__error">{error}</span>}
    </div>
  );
}
