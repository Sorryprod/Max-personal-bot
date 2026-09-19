import { useState } from 'react';
import { Button, Typography } from '@maxhub/max-ui';
import { closeApp } from '../bridge';
import { copyText } from '../format';
import type { Vacancy } from '../types';

export function VacancyCreated({ vacancy, onDone }: { vacancy: Vacancy; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="page state">
      <div className="state__icon">✅</div>
      <Typography.Title>Вакансия опубликована</Typography.Title>
      <Typography.Body className="muted">
        «{vacancy.position}». Перешлите ссылку в городские чаты — кандидаты откликнутся прямо в боте. Ссылка также
        отправлена вам в чат.
      </Typography.Body>
      <div className="link-box">{vacancy.invite_link}</div>
      <Button stretched onClick={async () => setCopied(await copyText(vacancy.invite_link))}>
        {copied ? 'Скопировано ✓' : 'Скопировать ссылку'}
      </Button>
      <Button stretched variant="secondary" onClick={onDone}>
        К моим вакансиям
      </Button>
      <Button stretched variant="ghost" onClick={closeApp}>
        Вернуться в чат
      </Button>
    </div>
  );
}
