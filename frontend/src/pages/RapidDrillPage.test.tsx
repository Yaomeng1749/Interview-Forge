import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LocaleProvider } from '../i18n/i18n'
import { RapidDrillPage } from './RapidDrillPage'

const apiMock = vi.hoisted(() => ({
  startDrill: vi.fn(),
  nextDrill: vi.fn(),
  drillQuestion: vi.fn(),
  drillFeedback: vi.fn(),
  answerDrill: vi.fn(),
  finishDrill: vi.fn(),
  bookmarkQuestion: vi.fn(),
}))

vi.mock('../api/client', () => ({ api: apiMock }))

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <LocaleProvider><RapidDrillPage /></LocaleProvider>
    </QueryClientProvider>,
  )
}

describe('RapidDrillPage completion', () => {
  beforeEach(() => {
    apiMock.startDrill.mockResolvedValue({ id: 'drill-1', count: 20, locale: 'zh-CN' })
    apiMock.nextDrill.mockResolvedValue({
      id: 'q-20', position: 20, prompt: '2 + 2 = ?', type: 'fill_blank',
      domain: 'sde', topic: 'algorithms', concept: 'arithmetic', difficulty: 'L1',
    })
    apiMock.answerDrill.mockResolvedValue({
      question_id: 'q-20', correct: true, is_correct: true,
      correct_answer: '4', explanation: '2 + 2 = 4',
    })
    apiMock.drillQuestion.mockResolvedValue({
      id: 'q-20', position: 20, prompt: '2 + 2 = ?', type: 'fill_blank',
      domain: 'sde', topic: 'algorithms', concept: 'arithmetic', difficulty: 'L1',
    })
    apiMock.drillFeedback.mockResolvedValue({
      question_id: 'q-20', correct: true, is_correct: true,
      correct_answer: '4', explanation: '2 + 2 = 4',
    })
    apiMock.bookmarkQuestion.mockResolvedValue({ id: 'q-20', bookmarked: true })
    apiMock.finishDrill.mockResolvedValue({ id: 'drill-1', answered: 20, correct: 17, status: 'finished' })
  })

  it('finishes a finite run after its last answer and renders a summary', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: '20' }))
    await user.click(screen.getByRole('button', { name: /开始刷题/i }))
    await user.type(await screen.findByRole('textbox'), '4')
    await user.click(screen.getByRole('button', { name: /提交答案/i }))
    await user.click(await screen.findByRole('button', { name: /完成本轮/i }))

    expect(apiMock.finishDrill).toHaveBeenCalledWith('drill-1')
    expect(await screen.findByText('17 / 20')).toBeInTheDocument()
  })

  it('requests the active question in the interface locale', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: '20' }))
    await user.click(screen.getByRole('button', { name: /开始刷题/i }))

    expect(apiMock.nextDrill).toHaveBeenCalledWith('drill-1', 'zh-CN')
  })

  it('offers a bookmark control during rapid practice', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: '20' }))
    await user.click(screen.getByRole('button', { name: /开始刷题/i }))
    await user.click(await screen.findByRole('button', { name: /收藏此题/i }))

    expect(apiMock.bookmarkQuestion).toHaveBeenCalledWith('q-20', true)
  })
})
