import { useEffect, useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { api, ApiError } from './api';
import { bindBackButton, closeApp, isAuthorized, startParam } from './bridge';
import { EmptyState, ErrorState, Loading } from './components/States';
import { VacancyCreated } from './screens/VacancyCreated';
import { VacancyDetail } from './screens/VacancyDetail';
import { VacancyForm } from './screens/VacancyForm';
import { VacancyList } from './screens/VacancyList';
import type { Me, Vacancy } from './types';

type Screen =
  | { name: 'list' }
  | { name: 'new' }
  | { name: 'created'; vacancy: Vacancy }
  | { name: 'vacancy'; id: number };

function initialScreen(): Screen {
  // Параметр из ссылки https://max.ru/<бот>?startapp=new
  if (startParam === 'new') return { name: 'new' };
  const match = /^vacancy-(\d+)$/.exec(startParam);
  if (match) return { name: 'vacancy', id: Number(match[1]) };
  return { name: 'list' };
}

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [screen, setScreen] = useState<Screen>(initialScreen);

  const load = () => {
    setError(null);
    api.get<Me>('/me').then(setMe).catch((e: ApiError) => setError(e.message));
  };
  useEffect(() => {
    if (isAuthorized) load();
  }, []);

  useEffect(() => bindBackButton(screen.name === 'list' ? null : () => setScreen({ name: 'list' })), [screen]);

  if (!isAuthorized) {
    return <div className="page"><ErrorState message="Откройте это приложение из бота в MAX." /></div>;
  }
  if (error) return <div className="page"><ErrorState message={error} onRetry={load} /></div>;
  if (!me) return <div className="page"><Loading /></div>;
  if (!me.employer) {
    return (
      <div className="page">
        <EmptyState
          icon="🏪"
          title="Сначала расскажите о точке"
          hint="Вернитесь в чат с ботом, выберите «Я ищу сотрудников» и укажите название и город."
          action={<Button onClick={closeApp}>Вернуться в чат</Button>}
        />
      </div>
    );
  }

  const toList = () => setScreen({ name: 'list' });
  // Видимая «Назад» дублирует системную: в некоторых клиентах BackButton может не поддерживаться.
  const backBar = (
    <div className="backbar">
      <button type="button" className="chip" onClick={toList}>← Мои вакансии</button>
    </div>
  );

  switch (screen.name) {
    case 'new':
      return <>{backBar}<VacancyForm me={me} onCreated={(vacancy) => setScreen({ name: 'created', vacancy })} /></>;
    case 'created':
      return <VacancyCreated vacancy={screen.vacancy} onDone={toList} />;
    case 'vacancy':
      return <>{backBar}<VacancyDetail id={screen.id} /></>;
    default:
      return (
        <VacancyList
          me={me}
          onCreate={() => setScreen({ name: 'new' })}
          onOpen={(id) => setScreen({ name: 'vacancy', id })}
        />
      );
  }
}
