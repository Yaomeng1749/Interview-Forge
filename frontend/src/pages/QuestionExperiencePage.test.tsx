import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LocaleProvider } from '../i18n/i18n'
import { QuestionBankPage } from './QuestionBankPage'
import { ResultPage } from './ResultPage'
import { SettingsPage } from './SettingsPage'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const apiMock = vi.hoisted(() => ({
  questions: vi.fn(),
  previewQuestionImport: vi.fn(),
  importQuestions: vi.fn(),
  result: vi.fn(),
  settings: vi.fn(),
  providerStatus: vi.fn(),
  saveSettings: vi.fn(),
  testProviders: vi.fn(),
}))

vi.mock('../api/client', () => ({ api: apiMock }))

function renderWithClient(node: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><LocaleProvider>{node}</LocaleProvider></QueryClientProvider>)
}

describe('question quality surfaces', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.questions.mockResolvedValue({ total: 1, items: [{
      id: 'mle-curated-kv-cache-0001', domain: 'mle', topic: 'ml_systems_inference', concept: 'kv_cache',
      difficulty: 'L2', type: 'single_choice', prompt: 'Why does a KV cache reduce autoregressive decoding work?', verified: true,
      question_style: 'concept', quality_tier: 'curated', source_kind: 'curated',
    }] })
    apiMock.previewQuestionImport.mockResolvedValue({ valid_count: 2, invalid_count: 0, duplicate_count: 0, errors: [] })
    apiMock.importQuestions.mockResolvedValue({ imported_count: 2, skipped_count: 0 })
    apiMock.result.mockResolvedValue({
      exam_id: 'exam-1', score: 80, total_score: 100, correct_count: 1, total_questions: 1, elapsed_seconds: 60,
      choice_accuracy: 1, fill_accuracy: 0, difficulty_breakdown: { L2: 1 }, topic_breakdown: { ml_systems_inference: 1 },
      questions: [{
        id: 'mle-curated-kv-cache-0001', position: 1, prompt: 'Why does a KV cache reduce autoregressive decoding work?',
        type: 'single_choice', difficulty: 'L2', topic: 'ml_systems_inference', concept: 'kv_cache',
        user_answer: 'B', correct_answer: 'A', correct: false, explanation: 'The cache reuses past keys and values.',
        distractor_explanations: { B: 'Caching logits alone does not avoid recomputing past attention states.' },
        takeaway: 'Cache K/V tensors, not only final logits.',
        knowledge_card: { summary: 'KV cache', why_it_matters: 'It controls decode latency.', interview_angle: 'Explain memory versus latency.', common_pitfall: 'It increases memory use.' },
      }],
    })
    apiMock.settings.mockResolvedValue({ daily_target: 40 })
    apiMock.providerStatus.mockResolvedValue({ active_provider: 'jev', jev: 'connected', nanojev: 'running', von: 'running' })
  })

  it('previews then imports a JSONL pack and labels curated question quality', async () => {
    const user = userEvent.setup()
    renderWithClient(<QuestionBankPage />)
    expect(await screen.findByText('Why does a KV cache reduce autoregressive decoding work?')).toBeInTheDocument()
    expect(screen.getByText('CURATED')).toBeInTheDocument()

    const file = new File(['{"id":"mle-curated-kv-cache-0001"}\n'], 'questions.jsonl', { type: 'application/x-ndjson' })
    const input = screen.getByLabelText(/选择 JSON|Choose JSON/i)
    await user.upload(input, file)
    await user.click(screen.getByRole('button', { name: /预览导入|Preview import/i }))
    expect(await screen.findByText(/2.*valid|有效.*2/i)).toBeInTheDocument()
    expect(apiMock.previewQuestionImport).toHaveBeenCalledWith({ filename: 'questions.jsonl', content: expect.stringContaining('kv-cache') })

    await user.click(screen.getByRole('button', { name: /确认导入|Confirm import/i }))
    expect(apiMock.importQuestions).toHaveBeenCalledWith({ filename: 'questions.jsonl', content: expect.any(String) })
    expect(await screen.findByText(/2.*imported|已导入.*2/i)).toBeInTheDocument()
  })

  it('shows the selected wrong-option reason and a bilingual knowledge card after an exam', async () => {
    renderWithClient(<MemoryRouter initialEntries={['/result/exam-1']}><Routes><Route path="/result/:id" element={<ResultPage />} /></Routes></MemoryRouter>)
    expect(await screen.findByText('Cache K/V tensors, not only final logits.')).toBeInTheDocument()
    expect(screen.getByText(/Caching logits alone/)).toBeInTheDocument()
    expect(screen.getByText('KV cache')).toBeInTheDocument()
    expect(screen.queryByText(/A.*The cache reuses/, { selector: 'li' })).not.toBeInTheDocument()
  })

  it('explains that Jev only adjusts difficulty and knowledge coverage', async () => {
    renderWithClient(<SettingsPage />)
    expect(await screen.findByText(/Jev.*难度.*知识覆盖|Jev.*difficulty.*knowledge coverage/i)).toBeInTheDocument()
    expect(screen.getByText(/不会.*A\s*\/\s*D\s*\/\s*G|cannot change.*A\s*\/\s*D\s*\/\s*G/i)).toBeInTheDocument()
  })
})
