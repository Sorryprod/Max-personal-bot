import { useEffect, useState } from 'react';
import { Button, CellList, CellSimple, Counter, Typography } from '@maxhub/max-ui';
import { api, ApiError } from '../api';
import { EmptyState, ErrorState, Loading } from '../components/States';
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
    api
      .get<Vacancy[]>('/vacancies')
      .then(setItems)
      .catch((e: ApiError) => setError(e.message));
  };
  useEffect(load, []);

  const header = (
    <div className="page-header">
      <div>
        <Typography.Title>Мои вакансии</Typography.Title>
        <Typography.Body className="muted">
          {me.employer?.place_name}, {me.employer?.city}
        </Typography.Body>
      </div>
    </div>
  );

  if (error) return <div className="page">{header}<ErrorState message={error} onRetry={load} /></div>;
  if (!items) return <div className="page">{header}<Loading /></div>;
  if (items.length === 0) {
    return (
      <div className="page">
        {header}
        <EmptyState
          icon="📋"
          title="Вакансий пока нет"
          hint="Создайте первую — я пришлю ссылку-приглашение, которую можно переслать в городские чаты."
          action={<Button onClick={onCreate}>Создать вакансию</Button>}
        />
      </div>
    );
  }

  return (
    <div className="page">
      {header}
      <Button stretched onClick={onCreate}>
        + Новая вакансия
      </Button>
      <CellList mode="island" filled className="list">
        {items.map((v) => (
          <CellSimple
            key={v.id}
            as="button"
            showChevron
            onClick={() => onOpen(v.id)}
            overline={v.status === 'closed' ? 'Закрыта' : undefined}
            title={v.position}
            subtitle={`${salaryText(v.salary_from, v.salary_to)} · ${v.total} ${plural(v.total, 'отклик', 'отклика', 'откликов')}`}
            after={v.unreviewed > 0 ? <Counter value={v.unreviewed} variant="attention" rounded /> : undefined}
          />
        ))}
      </CellList>
    </div>
  );
}
