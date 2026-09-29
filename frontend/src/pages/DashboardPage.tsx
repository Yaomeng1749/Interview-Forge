import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, BrainCircuit, Clock3, Crosshair, Flame, Play, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { PageHeader, QueryState } from '../components/QueryState'
import { useI18n } from '../i18n/i18n'

const pct = (value: number) => `${Math.round(value <= 1 ? value * 100 : value)}%`
const duration = (seconds: number) => `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`

export function DashboardPage() {
  const { t, locale } = useI18n()
  const query = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard, retry: 1 })
  const active = useQuery({ queryKey: ['active-exam'], queryFn: api.activeExam, retry: false })
  return <div className="page dashboard-page">
    <PageHeader eyebrow="TRAINING / 01" title={locale === 'zh-CN' ? '今天，完成一套真训练。' : 'Make today count under pressure.'} description={locale === 'zh-CN' ? '考场模式负责完整闭环；快速练习负责高吞吐。所有记录只保存在你的本机。' : 'Exam mode builds endurance. Rapid drill builds throughput. Your history stays local.'} actions={<Link className="button primary" to="/exams/new"><Play size={16}/>{t('action.start')}</Link>} />
    {active.data && <Link to={`/exam/${active.data.id}`} className="resume-strip"><span><i /> ACTIVE SESSION</span><strong>{t('action.resume')}</strong><ArrowUpRight size={18}/></Link>}
    <QueryState loading={query.isLoading} error={query.error} retry={() => query.refetch()}>
      {query.data && <>
        <section className="dashboard-grid">
          <article className="progress-card panel"><div className="panel-code">DAILY THROUGHPUT</div><div className="progress-value"><strong>{query.data.today_answered}</strong><span>/ {query.data.daily_goal ?? '∞'} {t('common.questions')}</span></div><div className="bar"><i style={{ width: `${Math.min(100, query.data.daily_goal ? query.data.today_answered / query.data.daily_goal * 100 : 15)}%` }} /></div><div className="split-meta"><span><Flame size={14}/>{query.data.today_exams} {t('dashboard.exams')}</span><span>{duration(query.data.today_seconds)}</span></div></article>
          <Metric icon={<Crosshair/>} label={t('dashboard.accuracy')} value={pct(query.data.today_accuracy)} accent="green" />
          <Metric icon={<Clock3/>} label={t('dashboard.time')} value={duration(query.data.today_seconds)} />
          <Metric icon={<RotateCcw/>} label={t('dashboard.review')} value={String(query.data.review_due)} accent="red" />
        </section>
        <section className="action-grid">
          <Action to="/exams/new" code="EXAM / STANDARD" title={t('action.start')} detail="40Q · 60M · 100P" />
          <Action to="/exams/new?streak=4" code="EXAM / ENDURANCE" title={t('action.four')} detail="4 × 40Q · 160 TOTAL" />
          <Action to="/drill" code="DRILL / RAPID" title={t('nav.drill')} detail="20 / 40 / 80 / 160 / ∞" />
          <Action to="/review" code="REVIEW / ERROR LOG" title={t('action.wrong')} detail={`${query.data.review_due} DUE`} />
        </section>
        <section className="mastery-section panel"><div><span className="panel-code">CAPABILITY MAP</span><h2>{t('dashboard.mastery')}</h2><p>{locale === 'zh-CN' ? `累计 ${query.data.total_answered} 题 · 历史正确率 ${pct(query.data.overall_accuracy)}` : `${query.data.total_answered} lifetime answers · ${pct(query.data.overall_accuracy)} accuracy`}</p></div><div className="mastery-pairs"><Mastery name="SDE" value={query.data.sde_mastery}/><Mastery name="MLE" value={query.data.mle_mastery}/></div><Link to="/learning-map" className="square-link"><BrainCircuit/><ArrowUpRight/></Link></section>
      </>}
    </QueryState>
  </div>
}

function Metric({ icon, label, value, accent = '' }: { icon: React.ReactNode; label: string; value: string; accent?: string }) { return <article className={`metric-card panel ${accent}`}><span>{icon}</span><small>{label}</small><strong>{value}</strong></article> }
function Action({ to, code, title, detail }: { to: string; code: string; title: string; detail: string }) { return <Link to={to} className="action-card"><small>{code}</small><strong>{title}</strong><span>{detail}<ArrowUpRight size={15}/></span></Link> }
function Mastery({ name, value }: { name: string; value: number }) { const normalized = value <= 1 ? value * 100 : value; return <div className="mastery"><div><strong>{name}</strong><span>{Math.round(normalized)}%</span></div><div className="bar"><i style={{ width: `${normalized}%` }}/></div></div> }
