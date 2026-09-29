import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { LocaleProvider } from './i18n/i18n'
import './styles/index.css'

const client = new QueryClient({defaultOptions:{queries:{staleTime:15_000,refetchOnWindowFocus:false}}})
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><LocaleProvider><BrowserRouter><App/></BrowserRouter></LocaleProvider></QueryClientProvider></React.StrictMode>)
