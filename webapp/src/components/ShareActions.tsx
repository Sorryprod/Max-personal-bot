import { useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { Check, Copy, Send } from 'lucide-react';
import { canShareToMax, shareToMax } from '../bridge';
import { copyText, salaryText } from '../format';
import type { Vacancy } from '../types';
import { Banner } from './States';
import { ICON } from './ui';

/** Готовый текст объявления для городского чата. */
export function inviteText(vacancy: Vacancy, place: string): string {
  return [
    `Ищем: ${vacancy.position} — ${place}`,
    `${salaryText(vacancy.salary_from, vacancy.salary_to)}, ${vacancy.schedule}`,
    `Адрес: ${vacancy.address}`,
    'Откликнуться за минуту, без резюме — по ссылке:',
  ].join('\n');
}

interface Props {
  vacancy: Vacancy;
  place: string;
  size?: 'medium' | 'large';
}

export function ShareActions({ vacancy, place, size = 'medium' }: Props) {
  const [copied, setCopied] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const copy = async () => {
    const ok = await copyText(vacancy.invite_link);
    setCopied(ok);
    return ok;
  };

  const share = async () => {
    setNotice(null);
    if (await shareToMax(inviteText(vacancy, place), vacancy.invite_link)) return;
    // Клиент не поддержал шеринг — не оставляем пользователя ни с чем.
    const ok = await copy();
    setNotice(ok ? 'Не удалось открыть «Поделиться» — ссылка скопирована, вставьте её в нужный чат.'
      : 'Не удалось открыть «Поделиться». Скопируйте ссылку вручную.');
  };

  return (
    <div className="stack">
      {canShareToMax && (
        <Button size={size} stretched iconBefore={<Send {...ICON} />} onClick={share}>
          Поделиться в MAX
        </Button>
      )}
      <Button size={size} stretched variant={canShareToMax ? 'secondary' : 'primary'}
        iconBefore={copied ? <Check {...ICON} /> : <Copy {...ICON} />} onClick={copy}>
        {copied ? 'Ссылка скопирована' : 'Скопировать ссылку'}
      </Button>
      {notice && <Banner kind="info">{notice}</Banner>}
    </div>
  );
}
