import { useEffect } from 'react';
import { Button } from '@maxhub/max-ui';
import { CircleCheck, Link2 } from 'lucide-react';
import { closeApp, haptic, webApp } from '../bridge';
import { ShareActions } from '../components/ShareActions';
import { ICON, IconCircle } from '../components/ui';
import type { Vacancy } from '../types';

export function VacancyCreated({ vacancy, place, onDone }: { vacancy: Vacancy; place: string; onDone: () => void }) {
  useEffect(() => {
    haptic('success');
  }, []);

  return (
    <div className="page">
      <div className="state" style={{ paddingBottom: 8 }}>
        <IconCircle icon={CircleCheck} />
        <h1 className="h1">Вакансия опубликована</h1>
        <p className="text muted">
          «{vacancy.position}». Отправьте ссылку в городской чат вакансий — кандидаты ответят на вопросы прямо
          в боте. Ссылка продублирована в чат с ботом.
        </p>
      </div>
      <div className="link-box">
        <Link2 {...ICON} />
        <span className="link-box__url">{vacancy.invite_link}</span>
      </div>
      <ShareActions vacancy={vacancy} place={place} size="large" />
      <div className="stack">
        <Button size="large" stretched variant="secondary" onClick={onDone}>К вакансиям</Button>
        {webApp?.initData && (
          <Button size="large" stretched variant="ghost" onClick={closeApp}>Вернуться в чат</Button>
        )}
      </div>
    </div>
  );
}
