import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, Bookmark, ChevronLeft, ChevronRight, Clock3, Send, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { QueryState } from '../components/QueryState'
import { useI18n } from '../i18n/i18n'
import { clearDraft, createDraft, recordAnswer, remainingSeconds, restoreDraft, toggleFlag, type ExamDraft } from '../lib/examState'

function formatTimer(total: number) { return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}` }

interface PendingAnswer { position: number; answer: string; revision: number }

export function ExamPage() {
  const { id = '' } = useParams(); const navigate = useNavigate(); const { t, locale } = useI18n()
  const query = useQuery({ queryKey: ['exam', id], queryFn: () => api.getExam(id), enabled: Boolean(id), retry: 1 })
  const [index, setIndex] = useState(0); const [draft, setDraft] = useState<ExamDraft | null>(null); const [seconds, setSeconds] = useState(0); const [saveState, setSaveState] = useState<'idle'|'saving'|'saved'|'error'>('idle'); const [confirming, setConfirming] = useState(false)
  const saveTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>())
  const pendingAnswers = useRef(new Map<number, PendingAnswer>())
  const saveChain = useRef<Promise<unknown>>(Promise.resolve())
  const flagRequests = useRef(new Set<Promise<unknown>>())
  const restoredExamId = useRef<string | null>(null)
  const persistAnswer = useCallback((payload: PendingAnswer) => {
    const request = saveChain.current.catch(() => undefined).then(() => api.saveAnswer(id, payload.position, payload.answer, payload.revision))
    saveChain.current = request
    request.then(() => setSaveState('saved'), () => setSaveState('error'))
    return request
  }, [id])
  useEffect(() => {
    if (!query.data || restoredExamId.current === id) return
    restoredExamId.current = id
    const local = restoreDraft(id)
    const base = local || createDraft(id, query.data.locale, query.data.duration_seconds)
    const serverRevisions = query.data.answer_revisions || {}
    const answerRevisions = { ...serverRevisions, ...base.answerRevisions }
    const merged = {
      ...base,
      revision: Math.max(base.revision, ...Object.values(serverRevisions), 0),
      answers: { ...query.data.answers, ...base.answers },
      answerRevisions,
      flags: Array.from(new Set([...(query.data.flags || []), ...base.flags])),
    }
    setDraft(merged)
    setSeconds(remainingSeconds(query.data.deadline_at))
    for (const [rawPosition, answer] of Object.entries(local?.answers || {})) {
      const position = Number(rawPosition)
      const revision = local?.answerRevisions[position] || local?.revision || 1
      if (revision > (serverRevisions[position] || 0) && answer !== query.data.answers?.[position]) {
        setSaveState('saving')
        void persistAnswer({ position, answer, revision })
      }
    }
  }, [query.data, id, persistAnswer])
  const flushPending = useCallback(async () => {
    for (const timer of saveTimers.current.values()) clearTimeout(timer)
    saveTimers.current.clear()
    const queued = [...pendingAnswers.current.values()].sort((left, right) => left.revision - right.revision)
    pendingAnswers.current.clear()
    const answerRequests = queued.map(persistAnswer)
    await Promise.all([...answerRequests, saveChain.current, ...flagRequests.current])
  }, [persistAnswer])
  const submit = useMutation({ mutationFn: async () => { await flushPending(); const revisions = draft?.answerRevisions || {}; return api.submitExam(id, Math.max(...Object.values(revisions), 0), revisions) }, onSuccess: () => { clearDraft(id); navigate(`/result/${id}`, { replace: true }) } })
  useEffect(() => { if (!query.data || submit.isPending) return; const timer = window.setInterval(() => setSeconds((current) => { if (current <= 1) { window.clearInterval(timer); submit.mutate(); return 0 } return current - 1 }), 1000); return () => window.clearInterval(timer) }, [query.data, submit])
  const question = query.data?.questions[index]
  const saveAnswer = (answer: string) => {
    if (!draft || !question) return
    const next = recordAnswer(draft, question.position, answer); setDraft(next); setSaveState('saving')
    const payload = { position: question.position, answer, revision: next.revision }
    pendingAnswers.current.set(question.position, payload)
    const existing = saveTimers.current.get(question.position)
    if (existing) clearTimeout(existing)
    saveTimers.current.set(question.position, setTimeout(() => {
      saveTimers.current.delete(question.position)
      const pending = pendingAnswers.current.get(question.position)
      if (!pending || pending.revision !== payload.revision) return
      pendingAnswers.current.delete(question.position)
      void persistAnswer(pending)
    }, 350))
  }
  const flag = () => {
    if (!draft || !question) return
    const next = toggleFlag(draft, question.position); setDraft(next); setSaveState('saving')
    const request = api.saveFlag(id, question.position, next.flags.includes(question.position), next.revision)
    flagRequests.current.add(request)
    request.then(() => setSaveState('saved'), () => setSaveState('error')).finally(() => flagRequests.current.delete(request))
  }
  const answeredCount = useMemo(() => Object.values(draft?.answers || {}).filter(Boolean).length, [draft])
  return <div className="exam-screen">
    <QueryState loading={query.isLoading || !draft} error={query.error} retry={() => query.refetch()}>
      {query.data && question && draft && <>
        <header className="exam-header"><div><span className="eyebrow">LIVE EXAM / {query.data.locale}</span><strong>{t('exam.frozen')}</strong></div><div className={`timer ${seconds < 300 ? 'critical' : ''}`}><Clock3/><span>{t('exam.remaining')}</span><strong>{formatTimer(seconds)}</strong></div><button className="button danger" onClick={() => setConfirming(true)}><Send size={16}/>{t('action.submit')}</button></header>
        <div className="exam-workspace">
          <section className="question-panel">
            <div className="question-meta"><span>{t('exam.question')} {question.position} / {query.data.questions.length}</span><div>{question.difficulty && <b>{question.difficulty}</b>}<b>{question.type === 'single_choice' ? 'SINGLE CHOICE' : 'FILL BLANK'}</b></div></div>
            <h1>{question.prompt}</h1>
            {question.type === 'single_choice' ? <div className="options">{question.options?.map((option) => <button key={option.id} className={draft.answers[question.position] === option.id ? 'selected' : ''} onClick={() => saveAnswer(option.id)}><span>{option.id}</span><p>{option.text}</p></button>)}</div> : <label className="fill-answer"><span>{locale === 'zh-CN' ? '输入答案' : 'Enter answer'}</span><input autoComplete="off" value={draft.answers[question.position] || ''} onChange={(e) => saveAnswer(e.target.value)} /></label>}
            <footer className="question-actions"><button className="button ghost" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}><ChevronLeft/>{t('action.previous')}</button><button className={`button flag ${draft.flags.includes(question.position) ? 'active' : ''}`} onClick={flag}><Bookmark/>{draft.flags.includes(question.position) ? t('action.unflag') : t('action.flag')}</button><button className="button primary" disabled={index === query.data.questions.length - 1} onClick={() => setIndex((i) => i + 1)}>{t('action.next')}<ChevronRight/></button></footer>
          </section>
          <aside className="navigator"><div className="navigator-head"><span>QUESTION GRID</span><strong>{answeredCount}/{query.data.questions.length}</strong></div><div className="question-grid">{query.data.questions.map((item, itemIndex) => <button key={item.id} aria-label={`${t('exam.question')} ${item.position}`} className={`${itemIndex === index ? 'current' : ''} ${draft.answers[item.position] ? 'answered' : ''} ${draft.flags.includes(item.position) ? 'flagged' : ''}`} onClick={() => setIndex(itemIndex)}>{item.position}</button>)}</div><div className="legend"><span><i/> {t('exam.unanswered')}</span><span><i className="answered"/> {t('exam.answered')}</span><span><i className="flagged"/> {t('exam.flagged')}</span></div><div className={`save-state ${saveState}`}><ShieldCheck/>{saveState === 'saving' ? t('status.saving') : saveState === 'error' ? t('status.saveFailed') : t('status.saved')}</div></aside>
        </div>
        {confirming && <div className="modal-backdrop" role="dialog" aria-modal="true"><div className="confirm-modal"><AlertTriangle/><span className="eyebrow">FINAL CHECK</span><h2>{locale === 'zh-CN' ? '确定交卷？' : 'Submit this exam?'}</h2><p>{locale === 'zh-CN' ? `已答 ${answeredCount} / ${query.data.questions.length}。提交后才会显示答案与解析。` : `${answeredCount} of ${query.data.questions.length} answered. Answers appear only after submission.`}</p><div><button className="button ghost" onClick={() => setConfirming(false)}>{locale === 'zh-CN' ? '返回检查' : 'Return'}</button><button className="button danger" disabled={submit.isPending} onClick={() => submit.mutate()}>{t('action.confirmSubmit')}</button></div>{submit.error && <p className="inline-error">{submit.error.message}</p>}</div></div>}
      </>}
    </QueryState>
  </div>
}
