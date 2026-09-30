import { useMutation } from '@tanstack/react-query'
import { ArrowRight, Bookmark, Check, Infinity as InfinityIcon, RotateCcw, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { PageHeader } from '../components/QueryState'
import { useI18n } from '../i18n/i18n'
import type { DrillFeedback, DrillQuestion, DrillSummary } from '../types'

function presentationOptions(question: DrillQuestion, sessionId: string) {
  const shuffled = [...(question.options || [])]
  let state = [...`${sessionId}:${question.id}`].reduce((value, character) => ((value * 31) + character.charCodeAt(0)) >>> 0, 2166136261)
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    state = ((state * 1664525) + 1013904223) >>> 0
    const swap = state % (index + 1)
    ;[shuffled[index], shuffled[swap]] = [shuffled[swap], shuffled[index]]
  }
  return shuffled.map((option, index) => ({ ...option, sourceId: option.id, displayId: String.fromCharCode(65 + index) }))
}

export function RapidDrillPage() {
  const { locale } = useI18n()
  const [count, setCount] = useState<number | null>(40)
  const [domain, setDomain] = useState('mixed')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chunkSize, setChunkSize] = useState(160)
  const [question, setQuestion] = useState<DrillQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [feedback, setFeedback] = useState<DrillFeedback | null>(null)
  const [summary, setSummary] = useState<DrillSummary | null>(null)
  const [completed, setCompleted] = useState(0)
  const [correct, setCorrect] = useState(0)
  const [advanceError, setAdvanceError] = useState<string | null>(null)

  const start = useMutation({
    mutationFn: () => api.startDrill({ count, domain, locale }),
    onSuccess: async (created) => {
      const first = await api.nextDrill(created.id, locale)
      setSessionId(created.id)
      setChunkSize(created.count)
      setCount(created.count)
      setQuestion(first)
      setCompleted(first.position - 1)
      setCorrect(0)
      setSummary(null)
    },
  })
  const submit = useMutation({
    mutationFn: () => api.answerDrill(sessionId!, { position: question!.position, answer, locale }),
    onSuccess: (data) => {
      setFeedback(data)
      setCompleted((value) => value + 1)
      if (data.correct) setCorrect((value) => value + 1)
    },
  })
  const bookmark = useMutation({
    mutationFn: () => api.bookmarkQuestion(question!.id, !question!.bookmarked),
    onSuccess: (saved) => setQuestion((current) => current ? { ...current, bookmarked: saved.bookmarked } : current),
  })

  const finishCurrent = async () => {
    const result = await api.finishDrill(sessionId!)
    setSummary(count === null ? { ...result, answered: completed, correct } : result)
    setQuestion(null)
  }

  const advance = async () => {
    try {
      setAdvanceError(null)
      if (count !== null && completed >= count) {
        await finishCurrent()
        return
      }
      if (count === null && question && question.position >= chunkSize) {
        await api.finishDrill(sessionId!)
        const created = await api.startDrill({ count: null, domain, locale })
        setSessionId(created.id)
        setChunkSize(created.count)
        setQuestion(await api.nextDrill(created.id, locale))
      } else {
        setQuestion(await api.nextDrill(sessionId!, locale))
      }
      setFeedback(null)
      setAnswer('')
    } catch (error) {
      setAdvanceError(error instanceof Error ? error.message : String(error))
    }
  }

  const reset = () => {
    setSessionId(null)
    setQuestion(null)
    setFeedback(null)
    setSummary(null)
    setAnswer('')
    setCompleted(0)
    setCorrect(0)
  }

  const questionId = question?.id
  const questionPosition = question?.position
  const feedbackQuestionId = feedback?.question_id

  useEffect(() => {
    if (!sessionId || !questionId || feedback) return
    let cancelled = false
    api.nextDrill(sessionId, locale).then((localized) => {
      if (!cancelled) setQuestion(localized)
    }).catch(() => undefined)
    return () => { cancelled = true }
  }, [feedback, locale, questionId, sessionId])

  useEffect(() => {
    if (!sessionId || !questionPosition || !feedbackQuestionId) return
    let cancelled = false
    Promise.all([
      api.drillQuestion(sessionId, questionPosition, locale),
      api.drillFeedback(sessionId, questionPosition, locale),
    ]).then(([localizedQuestion, localizedFeedback]) => {
      if (!cancelled) {
        setQuestion(localizedQuestion)
        setFeedback(localizedFeedback)
      }
    }).catch(() => undefined)
    return () => { cancelled = true }
  }, [feedbackQuestionId, locale, questionPosition, sessionId])

  const lastFiniteQuestion = count !== null && completed >= count
  const displayedOptions = question?.type === 'single_choice' ? presentationOptions(question, sessionId || '') : []
  const displayedCorrect = feedback && question?.type === 'single_choice'
    ? displayedOptions.find((option) => option.sourceId === feedback.correct_answer)?.displayId || feedback.correct_answer
    : feedback?.correct_answer
  return <div className="page">
    <PageHeader
      eyebrow="DRILL / RAPID"
      title={locale === 'zh-CN' ? '高吞吐快速练习' : 'High-throughput rapid drill'}
      description={locale === 'zh-CN' ? '每题提交后立即判分与解析；每 10 题刷新一次难度决策。' : 'Immediate grading after each answer. Difficulty decisions refresh every 10 questions.'}
    />
    {!sessionId ? <div className="drill-setup panel">
      <Zap/><h2>{locale === 'zh-CN' ? '选择本轮吞吐量' : 'Choose run volume'}</h2>
      <div className="segment">{[20, 40, 80, 160, null].map((item) => <button key={String(item)} className={count === item ? 'selected' : ''} onClick={() => setCount(item)}>{item ?? <InfinityIcon/>}</button>)}</div>
      <p className="muted">{locale === 'zh-CN' ? '只抽取从未作答的面试题，并随机排列；已做错或收藏的题请到复习队列。若新题不足，本轮会按实际可用题数开始。' : 'Only unseen interview questions are sampled and shuffled. Use Review Queue for incorrect or bookmarked questions. If fewer new questions are available, the run uses that smaller count.'}</p>
      <label className="field">DOMAIN<select value={domain} onChange={(event) => setDomain(event.target.value)}><option value="mixed">MLE + SDE</option><option value="mle">MLE</option><option value="sde">SDE</option></select></label>
      <button className="button primary" onClick={() => start.mutate()} disabled={start.isPending}>{locale === 'zh-CN' ? '开始刷题' : 'Start drill'}<ArrowRight/></button>
      {start.error && <p className="inline-error">{start.error.message}</p>}
    </div> : summary ? <section className="drill-card panel">
      <span className="eyebrow">DRILL COMPLETE</span>
      <h1>{locale === 'zh-CN' ? '本轮已完成' : 'Run complete'}</h1>
      <strong>{summary.correct} / {summary.answered}</strong>
      <p>{locale === 'zh-CN' ? `正确率 ${summary.answered ? Math.round(summary.correct / summary.answered * 100) : 0}%` : `${summary.answered ? Math.round(summary.correct / summary.answered * 100) : 0}% accuracy`}</p>
      <button className="button primary" onClick={reset}><RotateCcw/>{locale === 'zh-CN' ? '再来一轮' : 'Start another run'}</button>
    </section> : question && <section className="drill-card panel">
      <div className="drill-progress"><span>RAPID / {completed + 1}{chunkSize ? ` OF ${chunkSize}` : ''}</span><b>{question.difficulty} · {question.topic}</b></div>
      <div className="drill-question-heading"><h1>{question.prompt}</h1><button className={`icon-button drill-bookmark ${question.bookmarked ? 'saved' : ''}`} aria-label={question.bookmarked ? (locale === 'zh-CN' ? '取消收藏此题' : 'Remove question bookmark') : (locale === 'zh-CN' ? '收藏此题' : 'Bookmark this question')} title={question.bookmarked ? (locale === 'zh-CN' ? '已收藏' : 'Bookmarked') : (locale === 'zh-CN' ? '收藏本题以便回看' : 'Bookmark for review')} onClick={() => bookmark.mutate()} disabled={bookmark.isPending}><Bookmark fill={question.bookmarked ? 'currentColor' : 'none'}/></button></div>
      {question.type === 'single_choice' ? <div className="options compact">{displayedOptions.map((option) => <button key={option.sourceId} disabled={Boolean(feedback)} className={answer === option.sourceId ? 'selected' : ''} onClick={() => setAnswer(option.sourceId)}><span>{option.displayId}</span><p>{option.text}</p></button>)}</div> : <input className="rapid-input" disabled={Boolean(feedback)} value={answer} onChange={(event) => setAnswer(event.target.value)}/>}
      {!feedback ? <button className="button primary" disabled={!answer || submit.isPending} onClick={() => submit.mutate()}>{locale === 'zh-CN' ? '提交答案' : 'Submit answer'}</button> : <div className={`feedback ${feedback.correct ? 'correct' : 'wrong'}`}>
        <strong>{feedback.correct ? <><Check/>{locale === 'zh-CN' ? '正确' : 'Correct'}</> : locale === 'zh-CN' ? `错误 · 正确答案 ${displayedCorrect}` : `Incorrect · ${displayedCorrect}`}</strong>
        <p>{feedback.explanation}</p>
        {!feedback.correct && answer && feedback.distractor_explanations?.[answer] && <div className="targeted-distractor"><b>{locale === 'zh-CN' ? `你选的 ${answer} 为什么不对` : `Why your ${answer} answer is wrong`}</b><p>{feedback.distractor_explanations[answer]}</p></div>}
        {feedback.takeaway && <p className="takeaway"><b>{locale === 'zh-CN' ? '带走一句：' : 'Takeaway: '}</b>{feedback.takeaway}</p>}
        {feedback.knowledge_card && <aside className="knowledge-card"><span>KNOWLEDGE CARD</span>{feedback.knowledge_card.summary && <p><b>{locale === 'zh-CN' ? '核心概念' : 'Core concept'}</b>{feedback.knowledge_card.summary}</p>}{feedback.knowledge_card.why_it_matters && <p><b>{locale === 'zh-CN' ? '为什么重要' : 'Why it matters'}</b>{feedback.knowledge_card.why_it_matters}</p>}{feedback.knowledge_card.interview_angle && <p><b>{locale === 'zh-CN' ? '面试表达' : 'Interview angle'}</b>{feedback.knowledge_card.interview_angle}</p>}{feedback.knowledge_card.common_pitfall && <p><b>{locale === 'zh-CN' ? '常见误区' : 'Common pitfall'}</b>{feedback.knowledge_card.common_pitfall}</p>}</aside>}
        <button className="button primary" onClick={advance}>{lastFiniteQuestion ? (locale === 'zh-CN' ? '完成本轮' : 'Finish run') : (locale === 'zh-CN' ? '下一题' : 'Next question')}<ArrowRight/></button>
        {count === null && <button className="button ghost" onClick={finishCurrent}>{locale === 'zh-CN' ? '结束无限练习' : 'End infinite run'}</button>}
        {advanceError && <p className="inline-error">{advanceError}</p>}
      </div>}
    </section>}
  </div>
}
