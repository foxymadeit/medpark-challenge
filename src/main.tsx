import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { I18nProvider } from './i18n/I18nProvider';
import { AppStoreProvider } from './store/AppStore';
import './styles/base.css';
import './styles/components.css';
import './styles/layout.css';
import './styles/screens.css';
import './styles/responsive.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <AppStoreProvider>
        <App />
      </AppStoreProvider>
    </I18nProvider>
  </StrictMode>,
);
