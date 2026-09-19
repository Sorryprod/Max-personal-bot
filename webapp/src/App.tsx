import { Typography } from '@maxhub/max-ui';
import { webApp } from './bridge';

export function App() {
  const user = webApp?.initDataUnsafe.user;
  return (
    <div style={{ padding: 16 }}>
      <Typography.Title>Найм сотрудников</Typography.Title>
      <p>
        <Typography.Body>
          {user ? `Здравствуйте, ${user.first_name ?? ''}!` : 'Откройте приложение из бота в MAX.'}
        </Typography.Body>
      </p>
    </div>
  );
}
