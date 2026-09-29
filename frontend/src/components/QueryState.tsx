import type { ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'
import { useI18n } from '../i18n/i18n'

export function QueryState({ loading, error, retry, children }: { loading: boolean; error: unknown; retry?: () => void; children: ReactNode }) {
  const { t } = useI18n()
  if (loading) return <div className="system-state"><span className="loader" />{t('status.loading')}</div>
  if (error) return <div className="system-state error"><AlertTriangle/><strong>{t('status.offline')}</strong><p>{error instanceof Error ? error.message : t('error.generic')}</p>{retry && <button className="button ghost" onClick={retry}><RotateCcw size={15}/>{t('action.retry')}</button>}</div>
  return <>{children}</>
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</header>
}
