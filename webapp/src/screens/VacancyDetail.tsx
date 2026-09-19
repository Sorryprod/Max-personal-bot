import { useEffect, useMemo, useState } from 'react';
import { Button, Typography } from '@maxhub/max-ui';
import { api, ApiError } from '../api';
import { CandidateCard } from '../components/CandidateCard';
import { CompareTable } from '../components/CompareTable';
import { Banner, EmptyState, ErrorState, Loading } from '../components/States';
import { copyText, salaryText } from '../format';
import { FILTERS, type Filter } from '../statuses';
import type { Application, ApplicationStatus, Vacancy, VacancyApplications } from '../types';

export function VacancyDetail({ id }: { id: number }) {
  const [data, setData] = useState<VacancyApplications | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [filter, setFilter] = useState<Filter | null>(null);
  const [view, setView] = useState<'cards' | 'compare'>('cards');

  const load = () => {
    setError(null);
    api
      .get<VacancyApplications>(`/vacancies/${id}/applications`)
      .then(setData)
      .catch((e: ApiError) => setError(e.message));
  };
  useEffect(load, [id]);

  const apps = data?.applications ?? [];
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: apps.length };
    apps.forEach((a) => (c[a.status] = (c[a.status] ?? 0) + 1));
    return c;
  }, [apps]);
  // По умолчанию — те, кто ждёт решения; если таких нет — все.
  const activeFilter: Filter = filter ?? (counts.screened ? 'screened' : 'all');
  const visible = activeFilter === 'all' ? apps : apps.filter((a) => a.status === activeFilter);

  if (error) return <div className="page"><ErrorState message={error} onRetry={load} /></div>;
  if (!data) return <div className="page"><Loading /></div>;
  const { vacancy } = data;
  const questions = vacancy.questions ?? [];

  const changeStatus = async (app: Application, status: ApplicationStatus) => {
    setBusyId(app.id);
    setActionError(null);
    try {
      const updated = await api.patch<Application>(`/applications/${app.id}`, { status });
      setData((d) => d && { ...d, applications: d.applications.map((a) => (a.id === app.id ? updated : a)) });
    } catch (e) {
      setActionError((e as ApiError).message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="page">
      <div>
        <Typography.Title>{vacancy.position}</Typography.Title>
        <Typography.Body className="muted">
          {salaryText(vacancy.salary_from, vacancy.salary_to)} · {vacancy.schedule}
        </Typography.Body>
        <Typography.Body className="muted">📍 {vacancy.address}</Typography.Body>
      </div>
      {vacancy.status === 'closed' && <Banner kind="error">Вакансия закрыта — ссылка не принимает новые отклики</Banner>}

      <div className="section">
        <Typography.Headline>Кандидаты</Typography.Headline>
        {apps.length === 0 ? (
          <EmptyState
            icon="👥"
            title="Откликов пока нет"
            hint="Перешлите ссылку-приглашение в городские чаты — отклики появятся здесь, а я пришлю уведомление."
            action={<CopyLink link={vacancy.invite_link} />}
          />
        ) : (
          <>
            <div className="chips">
              {FILTERS.filter((f) => f.key === 'all' || counts[f.key]).map((f) => (
                <button key={f.key} type="button" className={`chip ${activeFilter === f.key ? 'chip--on' : ''}`}
                  onClick={() => setFilter(f.key)}>
                  {f.label} · {counts[f.key] ?? 0}
                </button>
              ))}
            </div>
            <div className="segmented">
              <button type="button" className={`chip ${view === 'cards' ? 'chip--on' : ''}`} onClick={() => setView('cards')}>
                Карточки
              </button>
              <button type="button" className={`chip ${view === 'compare' ? 'chip--on' : ''}`} onClick={() => setView('compare')}>
                Сравнить
              </button>
            </div>
            {actionError && <Banner kind="error">{actionError}</Banner>}
            {visible.length === 0 ? (
              <Typography.Body className="muted">В этой группе никого нет.</Typography.Body>
            ) : view === 'compare' ? (
              <CompareTable apps={visible} questions={questions} busyId={busyId} onStatus={changeStatus} />
            ) : (
              visible.map((app) => (
                <CandidateCard key={app.id} app={app} questions={questions} busy={busyId === app.id}
                  onStatus={(status) => changeStatus(app, status)} />
              ))
            )}
          </>
        )}
      </div>

      <VacancySettings vacancy={vacancy} onChange={(v) => setData((d) => d && { ...d, vacancy: v })} />
    </div>
  );
}

function CopyLink({ link }: { link: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button variant="secondary" stretched onClick={async () => setCopied(await copyText(link))}>
      {copied ? 'Скопировано ✓' : 'Скопировать ссылку'}
    </Button>
  );
}

function VacancySettings({ vacancy, onChange }: { vacancy: Vacancy; onChange: (v: Vacancy) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      const status = vacancy.status === 'active' ? 'closed' : 'active';
      onChange(await api.patch<Vacancy>(`/vacancies/${vacancy.id}`, { status }));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="section">
      <Typography.Headline>Ссылка для кандидатов</Typography.Headline>
      <div className="link-box">{vacancy.invite_link}</div>
      <CopyLink link={vacancy.invite_link} />
      {vacancy.questions && vacancy.questions.length > 0 && (
        <>
          <Typography.Headline>Вопросы кандидатам</Typography.Headline>
          {vacancy.questions.map((q) => (
            <Typography.Body key={q.id}>• {q.text}{q.is_blocking ? ' (отсеивающий)' : ''}</Typography.Body>
          ))}
        </>
      )}
      {error && <Banner kind="error">{error}</Banner>}
      <Button variant={vacancy.status === 'active' ? 'secondary' : 'primary'} stretched loading={busy} disabled={busy}
        onClick={toggle}>
        {vacancy.status === 'active' ? 'Закрыть вакансию' : 'Открыть снова'}
      </Button>
    </div>
  );
}
