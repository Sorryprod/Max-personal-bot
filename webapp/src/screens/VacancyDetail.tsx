import { useEffect, useState } from 'react';
import { Button, Typography } from '@maxhub/max-ui';
import { api, ApiError } from '../api';
import { Banner, ErrorState, Loading } from '../components/States';
import { copyText, salaryText } from '../format';
import type { Vacancy } from '../types';

export function VacancyDetail({ id }: { id: number }) {
  const [vacancy, setVacancy] = useState<Vacancy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = () => {
    setError(null);
    api.get<Vacancy>(`/vacancies/${id}`).then(setVacancy).catch((e: ApiError) => setError(e.message));
  };
  useEffect(load, [id]);

  if (error) return <div className="page"><ErrorState message={error} onRetry={load} /></div>;
  if (!vacancy) return <div className="page"><Loading /></div>;

  const toggleStatus = async () => {
    setBusy(true);
    setActionError(null);
    try {
      const status = vacancy.status === 'active' ? 'closed' : 'active';
      setVacancy(await api.patch<Vacancy>(`/vacancies/${id}`, { status }));
    } catch (e) {
      setActionError((e as ApiError).message);
    } finally {
      setBusy(false);
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
        {vacancy.status === 'closed' && <Banner kind="error">Вакансия закрыта — ссылка не принимает новые отклики</Banner>}
      </div>

      <div className="section">
        <Typography.Headline>Ссылка для кандидатов</Typography.Headline>
        <div className="link-box">{vacancy.invite_link}</div>
        <Button variant="secondary" stretched onClick={async () => setCopied(await copyText(vacancy.invite_link))}>
          {copied ? 'Скопировано ✓' : 'Скопировать ссылку'}
        </Button>
      </div>

      {vacancy.questions && vacancy.questions.length > 0 && (
        <div className="section">
          <Typography.Headline>Вопросы кандидатам</Typography.Headline>
          {vacancy.questions.map((q) => (
            <Typography.Body key={q.id}>
              • {q.text}
              {q.is_blocking ? ' (отсеивающий)' : ''}
            </Typography.Body>
          ))}
        </div>
      )}

      {actionError && <Banner kind="error">{actionError}</Banner>}
      <Button variant={vacancy.status === 'active' ? 'secondary' : 'primary'} stretched loading={busy} disabled={busy}
        onClick={toggleStatus}>
        {vacancy.status === 'active' ? 'Закрыть вакансию' : 'Открыть снова'}
      </Button>
    </div>
  );
}
