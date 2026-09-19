const fmt = (v: number) => v.toLocaleString('ru-RU');

export function salaryText(from: number | null, to: number | null): string {
  if (from && to) return `${fmt(from)}–${fmt(to)} ₽`;
  if (from) return `от ${fmt(from)} ₽`;
  if (to) return `до ${fmt(to)} ₽`;
  return 'по договорённости';
}

export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

/** +79991234567 -> +7 999 123-45-67; другие форматы возвращаются как есть. */
export function formatPhone(phone: string): string {
  const m = /^\+7(\d{3})(\d{3})(\d{2})(\d{2})$/.exec(phone);
  return m ? `+7 ${m[1]} ${m[2]}-${m[3]}-${m[4]}` : phone;
}
