import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowRight, Bookmark, CalendarClock, CircleX } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { PageHeader, QueryState } from '../components/QueryState'
import { useI18n } from '../i18n/i18n'

export function ReviewQueuePage() {
  const { locale, t } = useI18n(); const navigate = useNavigate(); const [kind, setKind] = useState<'wrong'|'due'|'bookmarked'>('due'); const query = useQuery({ queryKey: ['review',kind,locale], queryFn: () => api.review(kind, locale), retry: 1 }); const build = useMutation({ mutationFn: () => api.buildReview(kind, locale), onSuccess: ({ id }) => navigate(`/exam/${id}`) })
  const tabs = [{id:'wrong',icon:CircleX},{id:'due',icon:CalendarClock},{id:'bookmarked',icon:Bookmark}] as const
  return <div className="page"><PageHeader eyebrow="REVIEW / QUEUE" title={t('nav.review')} description={locale === 'zh-CN' ? '把错误重新变成可训练的输入，而不是一张静态错题清单。' : 'Turn errors back into trainable inputs, not a static archive.'} actions={<button className="button primary" disabled={!query.data?.length || build.isPending} onClick={() => build.mutate()}>{t('action.wrong')}<ArrowRight/></button>}/><div className="review-tabs">{tabs.map(({id,icon:Icon}) => <button key={id} className={kind===id?'active':''} onClick={()=>setKind(id)}><Icon/>{id.toUpperCase()}</button>)}</div><QueryState loading={query.isLoading} error={query.error} retry={()=>query.refetch()}>{query.data && (query.data.length ? <div className="queue-list">{query.data.map((item,index)=><article key={item.id}><span>{String(index+1).padStart(2,'0')}</span><div><small>{item.domain.toUpperCase()} / {item.topic} / {item.concept}</small><strong>{item.prompt}</strong></div><em className={`level ${item.difficulty}`}>{item.difficulty}</em></article>)}</div>:<div className="system-state">{t('status.empty')}</div>)}</QueryState></div>
}
