import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'framer-motion';
import { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { Toaster } from 'react-hot-toast';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import i18n from './i18n';
import './index.css';
import { useUiStore } from './store/uiStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30000, retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: false },
  },
});

function Root() {
  const theme = useUiStore((state) => state.theme);
  const language = useUiStore((state) => state.language);

  useEffect(() => {
    if (i18n.language !== language) void i18n.changeLanguage(language);
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = language;
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      'content',
      theme === 'dark' ? '#06121d' : '#ebf2f7',
    );
  }, [theme, language]);

  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <ErrorBoundary><App /></ErrorBoundary>
      </MotionConfig>
      <Toaster position={language === 'ar' ? 'top-left' : 'top-right'} toastOptions={{ duration: 3500 }} />
    </QueryClientProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <Root />
);
