import { useEffect, useState, type ReactNode } from 'react';
import { Button, Input, Switch } from '@maxhub/max-ui';
import { CircleAlert, Plus, Trash2, X } from 'lucide-react';
import { api, ApiError } from '../api';
import { Banner } from '../components/States';
import { ICON } from '../components/ui';
import { load, remove, save } from '../storage';
import type { Me, QuestionDraft, QuestionType, Vacancy, VacancyDraft } from '../types';

const DRAFT_KEY = 'vacancy-draft';
const POSITIONS = ['Повар', 'Продавец', 'Официант', 'Курьер', 'Уборщик', 'Бариста', 'Кассир'];
const SCHEDULES = ['2/2', '5/2', '3/3', 'Гибкий график'];
const TYPE_LABELS: Record<QuestionType, string> = { yes_no: 'Да / нет', choice: 'Варианты', text: 'Свой ответ' };

const EMPTY: VacancyDraft = { position: '', schedule: '', salary_from: '', salary_to: '', address: '', questions: [] };

type Errors = Partial<Record<keyof VacancyDraft | `q${number}`, string>>;

function validate(d: VacancyDraft): Errors {
  const e: Errors = {};
  const len = (s: string) => s.trim().length;
  if (len(d.position) < 2 || len(d.position) > 100) e.position = 'Укажите должность: от 2 до 100 символов';
  if (len(d.schedule) < 2 || len(d.schedule) > 100) e.schedule = 'Укажите график: от 2 до 100 символов';
  if (len(d.address) < 5 || len(d.address) > 200) e.address = 'Укажите адрес: от 5 до 200 символов';
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

  useEffect(() => {
    save(DRAFT_KEY, draft);
  }, [draft]);

  const set = <K extends keyof VacancyDraft>(key: K, value: VacancyDraft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  const setQuestion = (i: number, patch: Partial<QuestionDraft>) =>
    set('questions', draft.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  const addQuestion = (q: QuestionDraft) => set('questions', [...draft.questions, q]);
  const full = draft.questions.length >= me.max_questions;
  const templates = me.question_templates.filter((t) => !draft.questions.some((q) => q.text === t.text));
  const hasDraft = JSON.stringify(draft) !== JSON.stringify(EMPTY);

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
      <header className="stack-s">
        <h1 className="h1">Новая вакансия</h1>
        {hasDraft && (
          <div className="with-action">
            <span className="small faint">Черновик сохраняется автоматически</span>
            <button type="button" className="icon-button small" onClick={() => { setDraft(EMPTY); setErrors({}); }}>
              Очистить
            </button>
          </div>
        )}
      </header>

      <section className="card">
        <Field label="Должность" error={errors.position}>
          <Input value={draft.position} placeholder="Например, повар" onChange={(e) => set('position', e.target.value)} />
          <Chips items={POSITIONS} value={draft.position} onPick={(v) => set('position', v)} />
        </Field>
        <Field label="График" error={errors.schedule}>
          <Input value={draft.schedule} placeholder="Например, 2/2 с 9 до 21" onChange={(e) => set('schedule', e.target.value)} />
          <Chips items={SCHEDULES} value={draft.schedule} onPick={(v) => set('schedule', v)} />
        </Field>
      </section>

      <section className="card">
        <div className="row">
          <Field label="Зарплата от, ₽" error={errors.salary_from}>
            <Input inputMode="numeric" value={draft.salary_from} placeholder="40 000"
              onChange={(e) => set('salary_from', e.target.value.replace(/\D/g, ''))} />
          </Field>
          <Field label="до, ₽" error={errors.salary_to}>
            <Input inputMode="numeric" value={draft.salary_to} placeholder="60 000"
              onChange={(e) => set('salary_to', e.target.value.replace(/\D/g, ''))} />
          </Field>
        </div>
        <Field label="Адрес" error={errors.address}>
          <Input value={draft.address} placeholder={`${me.employer?.city ?? 'Город'}, улица, дом`}
            onChange={(e) => set('address', e.target.value)} />
        </Field>
      </section>

      <section className="stack">
        <div className="stack-s">
          <h2 className="h2">Вопросы кандидатам</h2>
          <p className="small muted">
            До {me.max_questions} вопросов. Кандидат отвечает кнопками в чате, а вы сразу видите, кто не подходит.
          </p>
        </div>

        {draft.questions.map((q, i) => (
          <QuestionEditor key={i} index={i} q={q} error={errors[`q${i}`]}
            onChange={(patch) => setQuestion(i, patch)}
            onRemove={() => set('questions', draft.questions.filter((_, j) => j !== i))} />
        ))}

        {!full && (
          <div className="stack">
            {templates.slice(0, 4).map((t) => (
              <button key={t.text} type="button" className="template" onClick={() => addQuestion({ ...t })}>
                <Plus {...ICON} />
                <span>{t.text}</span>
                <span className="template__type">{t.is_blocking ? 'отсеивает' : TYPE_LABELS[t.qtype]}</span>
              </button>
            ))}
            <button type="button" className="add-link"
              onClick={() => addQuestion({ text: '', qtype: 'yes_no', options: [], is_blocking: false, accepted: [] })}>
              <Plus {...ICON} />
              Свой вопрос
            </button>
          </div>
        )}
      </section>

      <div className="bottom-bar">
        {serverError && <Banner>{serverError}</Banner>}
        <Button size="large" stretched loading={submitting} disabled={submitting} onClick={submit}>
          Опубликовать
        </Button>
      </div>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="label">{label}</span>
      {children}
      {error && (
        <span className="field__error">
          <CircleAlert size={14} strokeWidth={2} />
          {error}
        </span>
      )}
    </label>
  );
}

function Chips({ items, value, onPick }: { items: string[]; value: string; onPick: (v: string) => void }) {
  return (
    <div className="chips">
      {items.map((item) => (
        <button key={item} type="button" className={`chip ${value === item ? 'chip--on' : ''}`} onClick={() => onPick(item)}>
          {item}
        </button>
      ))}
    </div>
  );
}

interface EditorProps {
  index: number;
  q: QuestionDraft;
  error?: string;
  onChange: (patch: Partial<QuestionDraft>) => void;
  onRemove: () => void;
}

function QuestionEditor({ index, q, error, onChange, onRemove }: EditorProps) {
  const answers = q.qtype === 'yes_no' ? [['yes', 'Да'], ['no', 'Нет']] : q.options.filter(Boolean).map((o) => [o, o]);
  const toggleAccepted = (value: string) =>
    onChange({ accepted: q.accepted.includes(value) ? q.accepted.filter((a) => a !== value) : [...q.accepted, value] });
  const changeType = (t: QuestionType) =>
    onChange({
      qtype: t,
      accepted: [],
      is_blocking: t === 'text' ? false : q.is_blocking,
      options: t === 'choice' && q.options.length < 2 ? ['', ''] : q.options,
    });

  return (
    <div className="card">
      <div className="with-action">
        <span className="label">Вопрос {index + 1}</span>
        <button type="button" className="icon-button icon-button--danger" aria-label="Удалить вопрос" onClick={onRemove}>
          <Trash2 {...ICON} />
        </button>
      </div>
      <Input value={q.text} placeholder="Текст вопроса" onChange={(e) => onChange({ text: e.target.value })} />

      <div className="segmented" role="group" aria-label="Тип ответа">
        {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => (
          <button key={t} type="button" aria-pressed={q.qtype === t} onClick={() => changeType(t)}>
            {TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      {q.qtype === 'choice' && (
        <div className="options">
          {q.options.map((opt, i) => (
            <div key={i} className="with-action">
              <Input value={opt} placeholder={`Вариант ${i + 1}`}
                onChange={(e) => onChange({
                  options: q.options.map((o, j) => (j === i ? e.target.value : o)),
                  accepted: q.accepted.filter((a) => a !== opt),
                })} />
              {q.options.length > 2 && (
                <button type="button" className="icon-button" aria-label="Удалить вариант"
                  onClick={() => onChange({
                    options: q.options.filter((_, j) => j !== i),
                    accepted: q.accepted.filter((a) => a !== opt),
                  })}>
                  <X {...ICON} />
                </button>
              )}
            </div>
          ))}
          {q.options.length < 6 && (
            <button type="button" className="add-link" onClick={() => onChange({ options: [...q.options, ''] })}>
              <Plus {...ICON} />
              Вариант
            </button>
          )}
        </div>
      )}

      {q.qtype !== 'text' && (
        <label className="switch-row">
          <span>Отсеивающий вопрос</span>
          <Switch checked={q.is_blocking}
            onChange={(e) => onChange({
              is_blocking: e.target.checked,
              accepted: e.target.checked && q.qtype === 'yes_no' ? ['yes'] : [],
            })} />
        </label>
      )}

      {q.is_blocking && (
        <div className="stack-s">
          <span className="label">Подходящие ответы</span>
          <div className="chips">
            {answers.map(([value, label]) => (
              <button key={value} type="button" className={`chip ${q.accepted.includes(value!) ? 'chip--on' : ''}`}
                onClick={() => toggleAccepted(value!)}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      {error && (
        <span className="field__error">
          <CircleAlert size={14} strokeWidth={2} />
          {error}
        </span>
      )}
    </div>
  );
}
