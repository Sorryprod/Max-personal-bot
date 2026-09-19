import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MaxUI } from '@maxhub/max-ui';
import '@fontsource-variable/onest/wght.css';
import '@maxhub/max-ui/dist/styles.css';
import './styles.css';
import { App } from './App';
import { webApp } from './bridge';

webApp?.ready?.();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MaxUI className="theme">
      <App />
    </MaxUI>
  </StrictMode>,
);
