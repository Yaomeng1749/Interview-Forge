import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, RefreshCw, Shield } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { PageHeader, QueryState } from '../components/QueryState'
import { LocaleToggle, useI18n } from '../i18n/i18n'

export function SettingsPage() {
  const { locale, t } = useI18n()
  const client = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings, retry: 1 })
  const providers = useQuery({ queryKey: ['providers'], queryFn: api.providerStatus, retry: 1 })
  const [goal, setGoal] = useState('160')

  useEffect(() => {
    if (settings.data?.daily_target !== undefined) {
      setGoal(String(settings.data.daily_target ?? 'unlimited'))
    }
  }, [settings.data])

  const save = useMutation({
    mutationFn: () => api.saveSettings({ locale, daily_target: goal === 'unlimited' ? 0 : Number(goal) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['settings'] }),
  })
  const test = useMutation({
    mutationFn: api.testProviders,
    onSuccess: () => client.invalidateQueries({ queryKey: ['providers'] }),
  })

  return <div className="page">
    <PageHeader
      eyebrow="SYSTEM / LOCAL CONFIG"
      title={t('nav.settings')}
      description={locale === 'zh-CN'
        ? '这里只保存训练偏好。Provider 密钥不会进入浏览器或 SQLite。'
        : 'Only training preferences live here. Provider secrets never enter the browser or SQLite.'}
    />
    <div className="settings-grid">
      <section className="panel settings-panel">
        <span className="panel-code">INTERFACE</span>
        <h2>{t('settings.language')}</h2>
        <LocaleToggle />
        <h2>{t('settings.goal')}</h2>
        <div className="segment wrap">
          {['40', '80', '120', '160', '200', 'unlimited'].map((value) =>
            <button key={value} className={goal === value ? 'selected' : ''} onClick={() => setGoal(value)}>
              {value === 'unlimited' ? '∞' : value}
            </button>)}
        </div>
        <button className="button primary" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isSuccess ? <><CheckCircle2 />{locale === 'zh-CN' ? '已保存' : 'Saved'}</> : locale === 'zh-CN' ? '保存偏好' : 'Save preferences'}
        </button>
      </section>
      <section className="panel settings-panel">
        <div className="provider-title">
          <div><span className="panel-code">DECISION ROUTER</span><h2>{t('settings.provider')}</h2></div>
          <button
            className="icon-button"
            aria-label={locale === 'zh-CN' ? '测试决策 Provider' : 'Test decision providers'}
            onClick={() => test.mutate()}
            disabled={test.isPending}
          ><RefreshCw /></button>
        </div>
        <QueryState loading={providers.isLoading} error={providers.error} retry={() => providers.refetch()}>
          {providers.data && <div className="providers">
            <Provider name="JEV" state={providers.data.jev} />
            <Provider name="NANOJEV" state={providers.data.nanojev} />
            <Provider name="VON" state={providers.data.von} />
            <div className="active-provider">
              <span>{locale === 'zh-CN' ? '最近使用' : 'LAST USED PROVIDER'}</span>
              <strong>{providers.data.active_provider}</strong>
            </div>
          </div>}
        </QueryState>
        <p className="adaptation-note">{locale === 'zh-CN'
          ? 'Jev 根据作答表现选择下一阶段的难度配比；本地规则安排知识点优先级。你选定的 A / D / G 卷型不变。'
          : 'Jev chooses the next difficulty mix from your results; local rules prioritize topics. Your A / D / G track stays fixed.'}</p>
        <p className="adaptation-note">{locale === 'zh-CN'
          ? '动态卷在建卷前决策，连续套卷在交卷后更新下一卷；Rapid 每答 10 题重排后续题目。固定精选卷不受影响。Jev 不生成、翻译或判题。'
          : 'Generated exams adapt before building, multi-paper runs update after submission, and Rapid refreshes the next block every 10 answers. Fixed curated papers stay unchanged. Jev does not write, translate, or grade questions.'}</p>
        <p className="secret-note"><Shield />{t('settings.secret')}</p>
      </section>
    </div>
  </div>
}

function Provider({ name, state }: { name: string; state: string }) {
  const good = ['connected', 'running'].includes(state)
  return <div className="provider-row">
    <span><i className={good ? 'good' : ''} />{name}</span>
    <b>{state.replace('_', ' ').toUpperCase()}</b>
  </div>
}
