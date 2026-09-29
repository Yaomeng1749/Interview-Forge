import type { Locale } from '../types'

export interface ExamDraft {
  examId: string
  locale: Locale
  revision: number
  durationSeconds: number
  answers: Record<number, string>
  answerRevisions: Record<number, number>
  flags: number[]
  updatedAt: string
}

export function createDraft(examId: string, locale: Locale, durationSeconds: number): ExamDraft {
  return { examId, locale, revision: 0, durationSeconds, answers: {}, answerRevisions: {}, flags: [], updatedAt: new Date().toISOString() }
}

function persist(draft: ExamDraft): ExamDraft {
  localStorage.setItem(`exam:draft:${draft.examId}`, JSON.stringify(draft))
  return draft
}

export function recordAnswer(draft: ExamDraft, position: number, answer: string): ExamDraft {
  const revision = draft.revision + 1
  return persist({ ...draft, revision, answers: { ...draft.answers, [position]: answer }, answerRevisions: { ...draft.answerRevisions, [position]: revision }, updatedAt: new Date().toISOString() })
}

export function toggleFlag(draft: ExamDraft, position: number): ExamDraft {
  const flags = draft.flags.includes(position) ? draft.flags.filter((item) => item !== position) : [...draft.flags, position]
  return persist({ ...draft, revision: draft.revision + 1, flags, updatedAt: new Date().toISOString() })
}

export function restoreDraft(examId: string): ExamDraft | null {
  try {
    const raw = localStorage.getItem(`exam:draft:${examId}`)
    if (!raw) return null
    const draft = JSON.parse(raw) as ExamDraft
    if (draft.examId !== examId || (draft.locale !== 'zh-CN' && draft.locale !== 'en-US')) return null
    return { ...draft, answerRevisions: draft.answerRevisions || {} }
  } catch {
    return null
  }
}

export function clearDraft(examId: string) {
  localStorage.removeItem(`exam:draft:${examId}`)
}

export function remainingSeconds(deadline: string, now = new Date()): number {
  return Math.max(0, Math.ceil((new Date(deadline).getTime() - now.getTime()) / 1000))
}
