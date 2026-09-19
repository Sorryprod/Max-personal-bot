import { useEffect, useMemo, useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { Check, Clock, Copy, LayoutList, Link2, ListChecks, Lock, LockOpen, MapPin, Table2, Users, Wallet } from 'lucide-react';
import { api, ApiError } from '../api';
import { CandidateCard } from '../components/CandidateCard';
import { CompareTable } from '../components/CompareTable';
import { Banner, EmptyState, ErrorState, Loading } from '../components/States';
import { ICON, Meta, Tag } from '../components/ui';
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
      <header className="stack">
        <div className="stack-s">
          {vacancy.status === 'closed' && <span><Tag>Закрыта</Tag></span>}
          <h1 className="h1">{vacancy.position}</h1>
        </div>
        <div className="meta">
          <Meta icon={Wallet}>{salaryText(vacancy.salary_from, vacancy.salary_to)}</Meta>
          <Meta icon={Clock}>{vacancy.schedule}</Meta>
          <Meta icon={MapPin}>{vacancy.address}</Meta>
        </div>
      </header>

      <section className="stack">
        <h2 className="h2">Кандидаты</h2>
        {apps.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={Users}
              title="Откликов пока нет"
              hint="Перешлите ссылку-приглашение в городские чаты — отклики появятся здесь, а бот пришлёт уведомление."
              actions={<CopyLink link={vacancy.invite_link} />}
            />
          </div>
        ) : (
          <>
            <div className="chips chips--scroll" role="tablist">
              {FILTERS.filter((f) => f.key === 'all' || counts[f.key]).map((f) => (
                <button key={f.key} type="button" role="tab" aria-selected={activeFilter === f.key}
                  className={`chip ${activeFilter === f.key ? 'chip--on' : ''}`} onClick={() => setFilter(f.key)}>
                  {f.label}
                  <span className="chip__count">{counts[f.key] ?? 0}</span>
                </button>
              ))}
            </div>
            <div className="segmented" role="group" aria-label="Вид">
              <button type="button" aria-pressed={view === 'cards'} onClick={() => setView('cards')}>
                <LayoutList size={16} strokeWidth={2} />
                Карточки
              </button>
              <button type="button" aria-pressed={view === 'compare'} onClick={() => setView('compare')}>
                <Table2 size={16} strokeWidth={2} />
                Сравнение
              </button>
            </div>
            {actionError && <Banner>{actionError}</Banner>}
            {visible.length === 0 ? (
              <p className="text muted">В этой группе никого нет.</p>
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
      </section>

      <VacancySettings vacancy={vacancy} onChange={(v) => setData((d) => d && { ...d, vacancy: v })} />
    </div>
  );
}

function CopyLink({ link }: { link: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button variant="secondary" stretched iconBefore={copied ? <Check {...ICON} /> : <Copy {...ICON} />}
      onClick={async () => setCopied(await copyText(link))}>
      {copied ? 'Ссылка скопирована' : 'Скопировать ссылку'}
    </Button>
  );
}

function VacancySettings({ vacancy, onChange }: { vacancy: Vacancy; onChange: (v: Vacancy) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = vacancy.status === 'active';

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(await api.patch<Vacancy>(`/vacancies/${vacancy.id}`, { status: active ? 'closed' : 'active' }));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="stack">
      <h2 className="h2">О вакансии</h2>
      <div className="card">
        <span className="label">Ссылка для кандидатов</span>
        <div className="link-box">
          <Link2 {...ICON} />
          <span className="link-box__url">{vacancy.invite_link}</span>
        </div>
        <CopyLink link={vacancy.invite_link} />
      </div>
      {vacancy.questions && vacancy.questions.length > 0 && (
        <div className="card">
          <span className="label">Вопросы кандидатам</span>
          <ul className="q-list">
            {vacancy.questions.map((q) => (
              <li key={q.id}>
                <ListChecks size={16} strokeWidth={2} />
                <span>
                  {q.text}
                  {q.is_blocking && <span className="faint"> · отсеивает</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <Banner>{error}</Banner>}
      <Button variant={active ? 'secondary' : 'primary'} size="large" stretched loading={busy} disabled={busy}
        iconBefore={active ? <Lock {...ICON} /> : <LockOpen {...ICON} />} onClick={toggle}>
        {active ? 'Закрыть вакансию' : 'Открыть снова'}
      </Button>
      {active && <p className="small faint">Закрытая вакансия перестаёт принимать отклики по ссылке.</p>}
    </section>
  );
}
