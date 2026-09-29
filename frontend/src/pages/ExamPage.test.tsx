import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LocaleProvider } from '../i18n/i18n'
import { ExamPage } from './ExamPage'

const apiMock = vi.hoisted(() => ({
  getExam: vi.fn().mockResolvedValue({ id: 'exam-1', locale: 'zh-CN', duration_seconds: 3600, deadline_at: '2099-01-01T00:00:00Z', questions: [{ id: 'q1', position: 1, prompt: '哈希表查询的平均复杂度？', type: 'single_choice', options: [{ id: 'A', text: 'O(1)' }, { id: 'B', text: 'O(n)' }] }] }),
  saveAnswer: vi.fn().mockResolvedValue({ saved: true }),
  saveFlag: vi.fn().mockResolvedValue({ saved: true }),
  submitExam: vi.fn().mockResolvedValue({}),
}))

vi.mock('../api/client', () => ({
  api: apiMock,
}))

describe('ExamPage secrecy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.getExam.mockResolvedValue({ id: 'exam-1', locale: 'zh-CN', duration_seconds: 3600, deadline_at: '2099-01-01T00:00:00Z', answers: {}, answer_revisions: {}, flags: [], questions: [{ id: 'q1', position: 1, prompt: '哈希表查询的平均复杂度？', type: 'single_choice', options: [{ id: 'A', text: 'O(1)' }, { id: 'B', text: 'O(n)' }] }] })
  })
  it('shows the prompt and controls but never answer or explanation', async () => {
    render(<QueryClientProvider client={new QueryClient()}><LocaleProvider><MemoryRouter initialEntries={['/exam/exam-1']}><Routes><Route path="/exam/:id" element={<ExamPage />} /></Routes></MemoryRouter></LocaleProvider></QueryClientProvider>)
    expect(await screen.findByText('哈希表查询的平均复杂度？')).toBeInTheDocument()
    expect(screen.queryByText(/正确答案|解析|Correct answer|Explanation/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /标记|Flag/i })).toBeInTheDocument()
  })

  it('flushes a just-selected answer before submitting', async () => {
    const user = userEvent.setup()
    render(<QueryClientProvider client={new QueryClient()}><LocaleProvider><MemoryRouter initialEntries={['/exam/exam-1']}><Routes><Route path="/exam/:id" element={<ExamPage />} /><Route path="/result/:id" element={<div>result</div>} /></Routes></MemoryRouter></LocaleProvider></QueryClientProvider>)
    await user.click(await screen.findByRole('button', { name: /O\(1\)/ }))
    await user.click(screen.getByRole('button', { name: /交卷|Submit/i }))
    await user.click(screen.getByRole('button', { name: /确认交卷|Confirm submit/i }))

    await waitFor(() => expect(apiMock.submitExam).toHaveBeenCalled())
    expect(apiMock.saveAnswer).toHaveBeenCalledWith('exam-1', 1, 'A', 1)
    expect(apiMock.saveAnswer.mock.invocationCallOrder[0])
      .toBeLessThan(apiMock.submitExam.mock.invocationCallOrder[0])
  })

  it('resynchronizes a local answer restored after a refresh', async () => {
    localStorage.setItem('exam:draft:exam-1', JSON.stringify({
      examId: 'exam-1', locale: 'zh-CN', revision: 2, durationSeconds: 3600,
      answers: { 1: 'B' }, answerRevisions: { 1: 2 }, flags: [], updatedAt: new Date().toISOString(),
    }))
    render(<QueryClientProvider client={new QueryClient()}><LocaleProvider><MemoryRouter initialEntries={['/exam/exam-1']}><Routes><Route path="/exam/:id" element={<ExamPage />} /></Routes></MemoryRouter></LocaleProvider></QueryClientProvider>)
    await screen.findByText('哈希表查询的平均复杂度？')
    await waitFor(() => expect(apiMock.saveAnswer).toHaveBeenCalledWith('exam-1', 1, 'B', 2))
  })
})
