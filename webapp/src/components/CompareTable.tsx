import { STATUS_LABELS } from '../statuses';
import type { Application, ApplicationStatus, Question } from '../types';

interface Props {
  apps: Application[];
  questions: Question[];
  busyId: number | null;
  onStatus: (app: Application, status: ApplicationStatus) => void;
}

/** Все кандидаты в одном экране: столбцы — кандидаты, строки — ответы, внизу — решение. */
export function CompareTable({ apps, questions, busyId, onStatus }: Props) {
  const answer = (app: Application, qid: number) => app.answers.find((a) => a.question_id === qid);
  return (
    <div className="compare">
      <table>
        <thead>
          <tr>
            <th />
            {apps.map((a) => (
              <th key={a.id} className={a.screening_failed ? 'cell--bad' : ''}>
                {a.name}
                <div className="small muted">{STATUS_LABELS[a.status]}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {questions.map((q) => (
            <tr key={q.id}>
              <th>{q.text}{q.is_blocking ? ' *' : ''}</th>
              {apps.map((a) => {
                const ans = answer(a, q.id);
                return (
                  <td key={a.id} className={ans && !ans.passed ? 'cell--bad' : ''}>
                    {ans ? ans.display : '—'}
                  </td>
                );
              })}
            </tr>
          ))}
          <tr>
            <th>Телефон</th>
            {apps.map((a) => (
              <td key={a.id}><a className="phone" href={`tel:${a.contact}`}>{a.contact}</a></td>
            ))}
          </tr>
          <tr>
            <th>Решение</th>
            {apps.map((a) => (
              <td key={a.id}>
                <select className="status-select" value={a.status === 'invited' ? 'invited' : a.status}
                  disabled={busyId === a.id || a.status === 'invited'}
                  onChange={(e) => onStatus(a, e.target.value as ApplicationStatus)}>
                  {a.status === 'invited' && <option value="invited">{STATUS_LABELS.invited}</option>}
                  <option value="screened">{STATUS_LABELS.screened}</option>
                  <option value="reserve">{STATUS_LABELS.reserve}</option>
                  <option value="rejected">{STATUS_LABELS.rejected}</option>
                </select>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
      {questions.some((q) => q.is_blocking) && <div className="small muted">* отсеивающий вопрос; красным — неподходящий ответ</div>}
    </div>
  );
}
