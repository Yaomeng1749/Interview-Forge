import { describe, expect, it } from 'vitest'
import { parseActiveExam, parseDashboard } from './guards'

describe('API response guards', () => {
  it('rejects active exam payloads that leak an answer or explanation', () => {
    const payload = { id: 'x', locale: 'zh-CN', questions: [{ id: 'q', position: 1, prompt: 'p', type: 'single_choice', answer: 'A' }] }
    expect(() => parseActiveExam(payload)).toThrow(/unsafe/i)
  })

  it('rejects malformed dashboard payloads with an actionable error', () => {
    expect(() => parseDashboard({ today_answered: 'many' })).toThrow(/dashboard/i)
  })

  it('normalizes a valid dashboard payload', () => {
    expect(parseDashboard({ today_answered: 40, daily_goal: null, today_exams: 1, today_accuracy: .8, today_seconds: 3600, total_answered: 400, overall_accuracy: .75, mle_mastery: .7, sde_mastery: .6, review_due: 12 })).toMatchObject({ today_answered: 40, daily_goal: null, review_due: 12 })
  })

  it('accepts a safe frozen exam and normalizes options', () => {
    expect(parseActiveExam({ id: 'e1', locale: 'en-US', duration_seconds: 3600, deadline_at: '2099-01-01T00:00:00Z', status: 'active', flags: [1, 'bad'], answers: { 1: 'A' }, questions: [{ id: 'q1', position: 1, prompt: 'Prompt', type: 'single_choice', difficulty: 'L2', domain: 'sde', topic: 'hash', concept: 'lookup', options: [{ id: 'A', text: 'O(1)' }] }, { id: 'q2', prompt: 'Fill', type: 'fill_blank' }] })).toMatchObject({ id: 'e1', locale: 'en-US', flags: [1], questions: [{ options: [{ id: 'A', text: 'O(1)' }] }, { position: 2 }] })
  })

  it('rejects invalid locale and question type', () => {
    expect(() => parseActiveExam({ id: 'e', locale: 'fr', questions: [] })).toThrow(/locale/i)
    expect(() => parseActiveExam({ id: 'e', locale: 'zh-CN', questions: [{ id: 'q', prompt: 'x', type: 'essay' }] })).toThrow(/question type/i)
  })
})
