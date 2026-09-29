import { useQuery } from '@tanstack/react-query'
import { CalendarClock, Target } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import { PageHeader, QueryState } from '../components/QueryState'
import { useI18n } from '../i18n/i18n'

const pct = (v: number) => `${Math.round(v <= 1 ? v * 100 : v)}%`
export function LearningMapPage() {
  const { locale, t } = useI18n(); const [domain, setDomain] = useState('all'); const query = useQuery({ queryKey: ['topics'], queryFn: api.topics, retry: 1 }); const data = query.data?.filter((item) => domain === 'all' || item.domain.toLowerCase() === domain)
  return <div className="page"><PageHeader eyebrow="MASTERY / TOPOLOGY" title={t('nav.map')} description={locale === 'zh-CN' ? '掌握度不是单次分数，而是知识点在长期训练中的稳定表现。' : 'Mastery tracks durable topic performance, not a single score.'} actions={<div className="segment small">{['all','sde','mle'].map((item) => <button key={item} className={domain === item ? 'selected' : ''} onClick={() => setDomain(item)}>{item.toUpperCase()}</button>)}</div>}/><QueryState loading={query.isLoading} error={query.error} retry={() => query.refetch()}>{data && (data.length ? <div className="topic-grid">{data.map((item) => <article key={item.id || item.topic} className="topic-card panel"><header><span>{item.domain.toUpperCase()}</span><b>{item.mastery <= 1 ? Math.round(item.mastery * 100) : Math.round(item.mastery)}%</b></header><h2>{item.topic}</h2><div className="bar"><i style={{ width: pct(item.mastery) }}/></div><dl><div><dt>{locale === 'zh-CN' ? '历史正确率' : 'Lifetime accuracy'}</dt><dd>{pct(item.accuracy)}</dd></div><div><dt>{locale === 'zh-CN' ? '近 7 天' : 'Last 7 days'}</dt><dd>{pct(item.recent_accuracy)}</dd></div><div><dt>{locale === 'zh-CN' ? '已答题' : 'Answered'}</dt><dd>{item.answered}</dd></div><div><dt>{locale === 'zh-CN' ? '错题' : 'Wrong'}</dt><dd className="bad">{item.wrong_count}</dd></div></dl><footer>{item.last_reviewed_at ? <><CalendarClock/> {new Date(item.last_reviewed_at).toLocaleDateString(locale)}</> : <><Target/> {locale === 'zh-CN' ? '尚未复习' : 'Not reviewed'}</>}</footer></article>)}</div> : <div className="system-state">{t('status.empty')}</div>)}</QueryState></div>
}
