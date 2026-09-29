import { parseActiveExam, parseDashboard } from './guards'
import type { ActiveExam, DashboardStats, DrillFeedback, DrillQuestion, DrillSummary, ExamResult, ExamTemplate, Locale, ProviderStatus, QuestionImportPreview, QuestionImportResult, QuestionSummary, TopicStat } from '../types'

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

const baseUrl = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  let body: unknown = null
  const text = await response.text()
  if (text) {
    try { body = JSON.parse(text) } catch { body = text }
  }
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? String((body as { detail: unknown }).detail) : `HTTP ${response.status}`
    throw new ApiError(response.status, detail)
  }
  return body
}

function unwrapList<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[]
  if (value && typeof value === 'object') {
    for (const key of ['items', 'results', 'data', 'questions', 'topics', 'templates']) {
      const list = (value as Record<string, unknown>)[key]
      if (Array.isArray(list)) return list as T[]
    }
  }
  throw new Error('Invalid list response from local API')
}

function importIssues(value: unknown): { line?: number; message: string; code?: string }[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (typeof item === 'string') return { message: item }
    if (!item || typeof item !== 'object') return { message: String(item) }
    const record = item as Record<string, unknown>
    return {
      ...(typeof record.line === 'number' ? { line: record.line } : {}),
      message: typeof record.message === 'string' ? record.message : typeof record.detail === 'string' ? record.detail : JSON.stringify(record),
      ...(typeof record.code === 'string' ? { code: record.code } : {}),
    }
  })
}

function parseImportPreview(value: unknown): QuestionImportPreview {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {}
  const count = (key: string, alternate: string) => typeof data[key] === 'number' ? data[key] as number : typeof data[alternate] === 'number' ? data[alternate] as number : 0
  return {
    valid_count: count('valid_count', 'valid'),
    invalid_count: count('invalid_count', 'invalid'),
    duplicate_count: count('duplicate_count', 'duplicates'),
    errors: importIssues(data.errors),
  }
}

function parseImportResult(value: unknown): QuestionImportResult {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {}
  return {
    imported_count: typeof data.imported_count === 'number' ? data.imported_count : typeof data.imported === 'number' ? data.imported : 0,
    skipped_count: typeof data.skipped_count === 'number' ? data.skipped_count : typeof data.skipped === 'number' ? data.skipped : 0,
    errors: importIssues(data.errors),
  }
}

export const api = {
  dashboard: async (): Promise<DashboardStats> => parseDashboard(await request('/api/stats/dashboard')),
  templates: async (locale: Locale): Promise<ExamTemplate[]> => unwrapList<ExamTemplate>(await request(`/api/exam-templates?locale=${encodeURIComponent(locale)}`)),
  activeExam: async (): Promise<ActiveExam | null> => {
    const value = await request('/api/exams/active')
    if (value === null) return null
    return parseActiveExam(value)
  },
  getExam: async (id: string): Promise<ActiveExam> => parseActiveExam(await request(`/api/exams/${encodeURIComponent(id)}`)),
  buildExam: async (payload: object): Promise<{ id: string }> => await request('/api/exams/build', { method: 'POST', body: JSON.stringify(payload) }) as { id: string },
  saveAnswer: async (id: string, position: number, answer: string, clientRevision: number) => request(`/api/exams/${encodeURIComponent(id)}/answers/${position}`, { method: 'PUT', body: JSON.stringify({ answer, client_revision: clientRevision }) }),
  saveFlag: async (id: string, position: number, flagged: boolean, clientRevision: number) => request(`/api/exams/${encodeURIComponent(id)}/flags/${position}`, { method: 'PUT', body: JSON.stringify({ flagged, client_revision: clientRevision }) }),
  submitExam: async (id: string, revision: number, answerRevisions: Record<number, number>) => request(`/api/exams/${encodeURIComponent(id)}/submit`, { method: 'POST', body: JSON.stringify({ client_revision: revision, answer_revisions: answerRevisions }) }),
  result: async (id: string): Promise<ExamResult> => await request(`/api/exams/${encodeURIComponent(id)}/result`) as ExamResult,
  startDrill: async (payload: object): Promise<{ id: string; count: number; locale: Locale }> => await request('/api/drill/session', { method: 'POST', body: JSON.stringify(payload) }) as { id: string; count: number; locale: Locale },
  nextDrill: async (id: string, locale: Locale): Promise<DrillQuestion> => await request(`/api/drill/${encodeURIComponent(id)}/next?locale=${encodeURIComponent(locale)}`) as DrillQuestion,
  drillQuestion: async (id: string, position: number, locale: Locale): Promise<DrillQuestion> => await request(`/api/drill/${encodeURIComponent(id)}/question/${position}?locale=${encodeURIComponent(locale)}`) as DrillQuestion,
  drillFeedback: async (id: string, position: number, locale: Locale): Promise<DrillFeedback> => await request(`/api/drill/${encodeURIComponent(id)}/feedback/${position}?locale=${encodeURIComponent(locale)}`) as DrillFeedback,
  answerDrill: async (id: string, payload: object): Promise<DrillFeedback> => await request(`/api/drill/${encodeURIComponent(id)}/answer`, { method: 'POST', body: JSON.stringify(payload) }) as DrillFeedback,
  bookmarkQuestion: async (id: string, bookmarked: boolean): Promise<{ id: string; bookmarked: boolean }> => await request(`/api/questions/${encodeURIComponent(id)}/bookmark`, { method: 'PUT', body: JSON.stringify({ bookmarked }) }) as { id: string; bookmarked: boolean },
  finishDrill: async (id: string): Promise<DrillSummary> => await request(`/api/drill/${encodeURIComponent(id)}/finish`, { method: 'POST' }) as DrillSummary,
  topics: async (): Promise<TopicStat[]> => unwrapList<TopicStat>(await request('/api/stats/topics')),
  questions: async (query: URLSearchParams): Promise<{ items: QuestionSummary[]; total: number }> => {
    const value = await request(`/api/questions?${query}`)
    if (Array.isArray(value)) return { items: value as QuestionSummary[], total: value.length }
    const data = value as { items?: QuestionSummary[]; results?: QuestionSummary[]; total?: number }
    const items = data.items || data.results || []
    return { items, total: typeof data.total === 'number' ? data.total : items.length }
  },
  previewQuestionImport: async (payload: { filename: string; content: string }): Promise<QuestionImportPreview> => parseImportPreview(await request('/api/questions/import/preview', { method: 'POST', body: JSON.stringify(payload) })),
  importQuestions: async (payload: { filename: string; content: string }): Promise<QuestionImportResult> => parseImportResult(await request('/api/questions/import', { method: 'POST', body: JSON.stringify(payload) })),
  review: async (kind: 'wrong' | 'due' | 'bookmarked', locale: Locale): Promise<QuestionSummary[]> => unwrapList<QuestionSummary>(await request(`/api/review/${kind}?locale=${encodeURIComponent(locale)}`)),
  buildReview: async (kind: string, locale: Locale) => request('/api/review/build-exam', { method: 'POST', body: JSON.stringify({ kind, locale }) }) as Promise<{ id: string }>,
  providerStatus: async (): Promise<ProviderStatus> => await request('/api/settings/provider/status') as ProviderStatus,
  testProviders: async (): Promise<ProviderStatus> => await request('/api/settings/provider/test', { method: 'POST' }) as ProviderStatus,
  settings: async () => await request('/api/settings') as Record<string, unknown>,
  saveSettings: async (payload: object) => request('/api/settings', { method: 'PUT', body: JSON.stringify(payload) }),
}
