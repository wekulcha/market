import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { initTelegramWebApp } from './telegram/initTelegram';

// Initialize Telegram WebApp before rendering
initTelegramWebApp();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
