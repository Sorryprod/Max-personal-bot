import { useEffect, useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { Briefcase, ChevronRight, Clock, MapPin, Plus, Wallet } from 'lucide-react';
import { api, ApiError } from '../api';
import { EmptyState, ErrorState, Loading } from '../components/States';
import { ICON, Meta, Tag } from '../components/ui';
import { plural, salaryText } from '../format';
import type { Me, Vacancy } from '../types';

interface Props {
  me: Me;
  onCreate: () => void;
  onOpen: (id: number) => void;
}

export function VacancyList({ me, onCreate, onOpen }: Props) {
  const [items, setItems] = useState<Vacancy[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    setItems(null);
    api.get<Vacancy[]>('/vacancies').then(setItems).catch((e: ApiError) => setError(e.message));
  };
  useEffect(load, []);

  const header = (
    <header className="stack-s" style={{ paddingTop: 12 }}>
      <span className="label">{me.employer?.place_name} · {me.employer?.city}</span>
      <h1 className="h1">Вакансии</h1>
    </header>
  );

  let body;
  if (error) body = <ErrorState message={error} onRetry={load} />;
  else if (!items) body = <Loading />;
  else if (items.length === 0) {
    body = (
      <EmptyState
        icon={Briefcase}
        title="Пока ни одной вакансии"
        hint="Создайте первую — бот пришлёт ссылку-приглашение, которую можно переслать в городские чаты."
        actions={<Button size="large" onClick={onCreate} iconBefore={<Plus {...ICON} />}>Создать вакансию</Button>}
      />
    );
  } else {
    const active = items.filter((v) => v.status === 'active');
    const closed = items.filter((v) => v.status === 'closed');
    body = (
      <>
        <Button size="large" stretched onClick={onCreate} iconBefore={<Plus {...ICON} />}>
          Новая вакансия
        </Button>
        <VacancyGroup items={active} onOpen={onOpen} />
        {closed.length > 0 && (
          <>
            <span className="label">Закрытые</span>
            <VacancyGroup items={closed} onOpen={onOpen} />
          </>
        )}
      </>
    );
  }

  return (
    <div className="page">
      {header}
      {body}
    </div>
  );
}

function VacancyGroup({ items, onOpen }: { items: Vacancy[]; onOpen: (id: number) => void }) {
  return (
    <div className="stack">
      {items.map((v) => (
        <button key={v.id} type="button" className="card card--tap" onClick={() => onOpen(v.id)}
          style={v.status === 'closed' ? { opacity: 0.7 } : undefined}>
          <div className="vacancy-card__head">
            <h2 className="h2">{v.position}</h2>
            {v.unreviewed > 0 && <Tag tone="accent">{v.unreviewed} {plural(v.unreviewed, 'новый', 'новых', 'новых')}</Tag>}
          </div>
          <div className="meta">
            <Meta icon={Wallet}>{salaryText(v.salary_from, v.salary_to)}</Meta>
            <Meta icon={Clock}>{v.schedule}</Meta>
            <Meta icon={MapPin}>{v.address}</Meta>
          </div>
          <div className="vacancy-card__stats">
            <span className="small muted">
              {v.total > 0 ? `${v.total} ${plural(v.total, 'отклик', 'отклика', 'откликов')}` : 'Откликов пока нет'}
            </span>
            <ChevronRight className="chev" size={18} />
          </div>
        </button>
      ))}
    </div>
  );
}
