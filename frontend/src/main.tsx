import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource-variable/inter'
import '@fontsource-variable/geist-mono'
import './index.css'
import App from './App.tsx'
import { SessionProvider } from '@/auth/SessionProvider'
import { LanguageProvider } from '@/i18n/LanguageProvider'

const storedTheme = localStorage.getItem('dmitri-theme')
document.documentElement.classList.toggle('dmitri-dark', storedTheme === 'dark')

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <LanguageProvider>
            <App />
          </LanguageProvider>
        </SessionProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
