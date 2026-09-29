import { describe, expect, it } from 'vitest'
import { clearDraft, createDraft, recordAnswer, remainingSeconds, restoreDraft, toggleFlag } from './examState'

describe('exam draft safety', () => {
  it('increments revisions monotonically for every answer edit', () => {
    const first = recordAnswer(createDraft('exam-7', 'zh-CN', 3_600), 1, 'A')
    const second = recordAnswer(first, 1, 'B')
    expect([first.revision, second.revision]).toEqual([1, 2])
    expect(second.answerRevisions).toEqual({ 1: 2 })
  })

  it('restores answers and frozen locale from local storage', () => {
    const draft = recordAnswer(createDraft('exam-7', 'en-US', 3_600), 2, 'hash map')
    localStorage.setItem('exam:draft:exam-7', JSON.stringify(draft))
    expect(restoreDraft('exam-7')).toMatchObject({ locale: 'en-US', answers: { 2: 'hash map' } })
  })

  it('derives remaining time from the server-aligned deadline', () => {
    expect(remainingSeconds('2026-09-21T18:01:00.000Z', new Date('2026-09-21T18:00:10.000Z'))).toBe(50)
    expect(remainingSeconds('2026-09-21T18:00:00.000Z', new Date('2026-09-21T18:00:10.000Z'))).toBe(0)
  })

  it('toggles flags and clears a completed draft', () => {
    const base = createDraft('exam-8', 'zh-CN', 3600)
    const flagged = toggleFlag(base, 3)
    expect(flagged.flags).toEqual([3])
    expect(toggleFlag(flagged, 3).flags).toEqual([])
    clearDraft('exam-8')
    expect(restoreDraft('exam-8')).toBeNull()
  })

  it('fails closed on corrupt or mismatched local drafts', () => {
    localStorage.setItem('exam:draft:bad', '{')
    expect(restoreDraft('bad')).toBeNull()
    localStorage.setItem('exam:draft:other', JSON.stringify({ examId: 'wrong', locale: 'zh-CN' }))
    expect(restoreDraft('other')).toBeNull()
  })
})
