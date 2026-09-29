import type { ActiveExam, DashboardStats, ExamQuestion, Locale, QuestionType } from '../types'

const unsafeKeys = new Set(['answer', 'correct_answer', 'correctness', 'explanation', 'grading_rule', 'grading_rules'])

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Invalid ${label} response`)
  return value as Record<string, unknown>
}

function number(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`Invalid ${label} in API response`)
  return value
}

function string(value: unknown, label: string): string {
  if (typeof value !== 'string' || value.length === 0) throw new Error(`Invalid ${label} in API response`)
  return value
}

function hasUnsafeKey(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  if (Array.isArray(value)) return value.some(hasUnsafeKey)
  return Object.entries(value as Record<string, unknown>).some(([key, child]) => unsafeKeys.has(key) || hasUnsafeKey(child))
}

export function parseDashboard(value: unknown): DashboardStats {
  const data = record(value, 'dashboard')
  return {
    today_answered: number(data.today_answered, 'dashboard.today_answered'),
    daily_goal: data.daily_goal === null || data.daily_goal === undefined ? null : number(data.daily_goal, 'dashboard.daily_goal'),
    today_exams: number(data.today_exams, 'dashboard.today_exams'),
    today_accuracy: number(data.today_accuracy, 'dashboard.today_accuracy'),
    today_seconds: number(data.today_seconds, 'dashboard.today_seconds'),
    total_answered: number(data.total_answered, 'dashboard.total_answered'),
    overall_accuracy: number(data.overall_accuracy, 'dashboard.overall_accuracy'),
    mle_mastery: number(data.mle_mastery, 'dashboard.mle_mastery'),
    sde_mastery: number(data.sde_mastery, 'dashboard.sde_mastery'),
    review_due: number(data.review_due, 'dashboard.review_due'),
  }
}

export function parseActiveExam(value: unknown): ActiveExam {
  if (hasUnsafeKey(value)) throw new Error('Unsafe in-progress exam response contains answer or explanation data')
  const data = record(value, 'active exam')
  if (data.locale !== 'zh-CN' && data.locale !== 'en-US') throw new Error('Invalid active exam locale')
  if (!Array.isArray(data.questions)) throw new Error('Invalid active exam questions')
  const questions: ExamQuestion[] = data.questions.map((raw, index) => {
    const q = record(raw, `question ${index + 1}`)
    const type = q.type as QuestionType
    if (type !== 'single_choice' && type !== 'fill_blank') throw new Error(`Invalid question type at ${index + 1}`)
    const options = q.options === undefined ? undefined : (q.options as unknown[]).map((rawOption) => {
      const option = record(rawOption, 'option')
      return { id: string(option.id, 'option.id'), text: string(option.text, 'option.text') }
    })
    return {
      id: string(q.id, 'question.id'),
      position: typeof q.position === 'number' ? q.position : index + 1,
      prompt: string(q.prompt, 'question.prompt'),
      type,
      options,
      domain: typeof q.domain === 'string' ? q.domain : undefined,
      topic: typeof q.topic === 'string' ? q.topic : undefined,
      concept: typeof q.concept === 'string' ? q.concept : undefined,
      difficulty: q.difficulty === 'L1' || q.difficulty === 'L2' || q.difficulty === 'L3' ? q.difficulty : undefined,
    }
  })
  return {
    id: string(data.id, 'exam.id'),
    locale: data.locale as Locale,
    duration_seconds: number(data.duration_seconds, 'exam.duration_seconds'),
    deadline_at: string(data.deadline_at, 'exam.deadline_at'),
    status: typeof data.status === 'string' ? data.status : undefined,
    questions,
    answers: data.answers && typeof data.answers === 'object' ? data.answers as Record<number, string> : undefined,
    answer_revisions: data.answer_revisions && typeof data.answer_revisions === 'object' ? data.answer_revisions as Record<number, number> : undefined,
    flags: Array.isArray(data.flags) ? data.flags.filter((item): item is number => typeof item === 'number') : undefined,
  }
}
