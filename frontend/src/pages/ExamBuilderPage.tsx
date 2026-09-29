import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { PageHeader, QueryState } from '../components/QueryState'
import { useI18n } from '../i18n/i18n'

const fallbackTemplates = [
  { id: 'exam-a-sde', name: 'A / SDE', description: 'Algorithms · OS · Network · DB · Backend' },
  { id: 'exam-d-mle', name: 'D / MLE', description: 'Statistics · ML · Evaluation · Deep Learning' },
  { id: 'exam-g-mixed', name: 'G / MIXED', description: '20 SDE + 20 MLE · Full simulation' },
  { id: 'curated-a1-sde', name: 'Curated A1 / SDE', description: 'Fixed 40-question SDE paper', fixed_pack: true },
  { id: 'curated-d1-mle', name: 'Curated D1 / MLE', description: 'Fixed 40-question MLE paper', fixed_pack: true },
  { id: 'curated-g1-mixed', name: 'Curated G1 / Mixed', description: 'Fixed 40-question mixed paper', fixed_pack: true },
  { id: 'curated-g2-mixed', name: 'Curated G2 / Mixed', description: 'Scenario and trade-off heavy mixed paper', fixed_pack: true },
]

export function ExamBuilderPage() {
  const { locale, t } = useI18n(); const navigate = useNavigate(); const [search] = useSearchParams()
  const templates = useQuery({ queryKey: ['templates', locale], queryFn: () => api.templates(locale), retry: 1 })
  const [templateId, setTemplateId] = useState('exam-g-mixed'); const [difficulty, setDifficulty] = useState('standard')
  const [timed, setTimed] = useState(true); const [reviewAllowed, setReviewAllowed] = useState(true); const [randomQuestions, setRandomQuestions] = useState(true); const [randomOptions, setRandomOptions] = useState(true)
  const list = useMemo(() => templates.data?.length ? templates.data : fallbackTemplates, [templates.data])
  const selectedTemplate = list.find((item) => item.id === templateId)
  const papers = search.get('streak') === '4' && !selectedTemplate?.fixed_pack ? 4 : 1
  const mutation = useMutation({ mutationFn: () => api.buildExam({ template_id: templateId, locale, difficulty_preset: difficulty, timed, allow_review: reviewAllowed, randomize_questions: randomQuestions, randomize_options: randomOptions, paper_count: papers }), onSuccess: (data) => navigate(`/exam/${data.id}`) })
  return <div className="page"><PageHeader eyebrow="EXAM / CONFIGURATION" title={locale === 'zh-CN' ? `${papers === 4 ? '连续四套' : '标准套卷'}配置` : `${papers === 4 ? 'Four-exam streak' : 'Standard exam'} setup`} description={locale === 'zh-CN' ? '开卷后题目、顺序与语言全部冻结，训练过程中不会动态换题。' : 'Questions, order, and locale freeze when the exam starts. No mid-exam adaptation.'}/>
    <QueryState loading={templates.isLoading} error={templates.data ? null : templates.error} retry={() => templates.refetch()}>
      <div className="builder-grid">
        <section className="panel config-section"><span className="panel-code">01 / TEMPLATE</span><h2>{locale === 'zh-CN' ? '选择卷型' : 'Choose paper'}</h2><div className="template-list">{list.map((item) => <button key={item.id} className={templateId === item.id ? 'selected' : ''} onClick={() => setTemplateId(item.id)}><span>{item.name}</span><small>{item.description}</small>{templateId === item.id && <Check/>}</button>)}</div></section>
        <section className="panel config-section"><span className="panel-code">02 / PARAMETERS</span><h2>{locale === 'zh-CN' ? '考场参数' : 'Exam parameters'}</h2>{selectedTemplate?.fixed_pack ? <p className="muted">{locale === 'zh-CN' ? '固定精选卷：题目集合、难度和答案均来自导入题包；Jev 不会替换题目。' : 'Fixed curated paper: questions, difficulty, and answers come from the imported pack; Jev will not replace questions.'}</p> : <label className="field">{locale === 'zh-CN' ? '难度预设' : 'Difficulty preset'}<select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}><option value="foundation">{locale === 'zh-CN' ? '基础卷' : 'Foundation'}</option><option value="standard">{locale === 'zh-CN' ? '标准卷' : 'Standard'}</option><option value="intensive">{locale === 'zh-CN' ? '强化卷' : 'Intensive'}</option><option value="hard">{locale === 'zh-CN' ? '高难卷' : 'Hard'}</option></select></label>}
          <Toggle checked={timed} set={setTimed} label={locale === 'zh-CN' ? '60 分钟计时' : '60-minute timer'}/><Toggle checked={reviewAllowed} set={setReviewAllowed} label={locale === 'zh-CN' ? '允许回看已答题' : 'Allow answered-question review'}/><Toggle checked={randomQuestions} set={setRandomQuestions} label={locale === 'zh-CN' ? '随机题序' : 'Randomize question order'}/><Toggle checked={randomOptions} set={setRandomOptions} label={locale === 'zh-CN' ? '随机选项顺序' : 'Randomize options'}/>
        </section>
        <aside className="launch-card"><span>MISSION BRIEF</span><strong>{papers * 40}</strong><small>{t('common.questions')} · {papers * 60} {t('common.minutes')}</small><dl><div><dt>CHOICE</dt><dd>{papers * 30}</dd></div><div><dt>FILL</dt><dd>{papers * 10}</dd></div><div><dt>SCORE</dt><dd>{papers * 100}</dd></div></dl><button className="button primary wide" disabled={mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? t('status.loading') : t('action.start')}<ChevronRight/></button>{mutation.error && <p className="inline-error"><AlertTriangle/>{mutation.error instanceof ApiError && mutation.error.status === 409 ? t('error.inventory') : mutation.error.message}</p>}</aside>
      </div>
    </QueryState>
  </div>
}

function Toggle({ checked, set, label }: { checked: boolean; set: (next: boolean) => void; label: string }) { return <label className="toggle-row"><span>{label}</span><input type="checkbox" checked={checked} onChange={(e) => set(e.target.checked)}/><i/></label> }
