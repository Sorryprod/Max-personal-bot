import { useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { Check, CircleCheck, Copy, Link2 } from 'lucide-react';
import { closeApp, webApp } from '../bridge';
import { ICON, IconCircle } from '../components/ui';
import { copyText } from '../format';
import type { Vacancy } from '../types';

export function VacancyCreated({ vacancy, onDone }: { vacancy: Vacancy; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="page">
      <div className="state" style={{ paddingBottom: 8 }}>
        <IconCircle icon={CircleCheck} />
        <h1 className="h1">Вакансия опубликована</h1>
        <p className="text muted">
          «{vacancy.position}». Перешлите ссылку в городские чаты — кандидаты ответят на вопросы прямо в боте.
          Ссылка продублирована в чат.
        </p>
      </div>
      <div className="link-box">
        <Link2 {...ICON} />
        <span className="link-box__url">{vacancy.invite_link}</span>
      </div>
      <div className="stack">
        <Button size="large" stretched iconBefore={copied ? <Check {...ICON} /> : <Copy {...ICON} />}
          onClick={async () => setCopied(await copyText(vacancy.invite_link))}>
          {copied ? 'Ссылка скопирована' : 'Скопировать ссылку'}
        </Button>
        <Button size="large" stretched variant="secondary" onClick={onDone}>К вакансиям</Button>
        {webApp?.initData && (
          <Button size="large" stretched variant="ghost" onClick={closeApp}>Вернуться в чат</Button>
        )}
      </div>
    </div>
  );
}
