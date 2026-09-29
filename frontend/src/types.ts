export type Locale = 'zh-CN' | 'en-US'
export type Difficulty = 'L1' | 'L2' | 'L3'
export type QuestionType = 'single_choice' | 'fill_blank'

export interface Option { id: string; text: string }

export interface ExamQuestion {
  id: string
  position: number
  prompt: string
  type: QuestionType
  options?: Option[]
  domain?: string
  topic?: string
  concept?: string
  difficulty?: Difficulty
}

export interface ActiveExam {
  id: string
  locale: Locale
  duration_seconds: number
  deadline_at: string
  status?: string
  questions: ExamQuestion[]
  answers?: Record<number, string>
  answer_revisions?: Record<number, number>
  flags?: number[]
}

export interface DashboardStats {
  today_answered: number
  daily_goal: number | null
  today_exams: number
  today_accuracy: number
  today_seconds: number
  total_answered: number
  overall_accuracy: number
  mle_mastery: number
  sde_mastery: number
  review_due: number
}

export interface ExamTemplate {
  id: string
  name: string
  description?: string
  question_count?: number
  duration_minutes?: number
  fixed_pack?: boolean
}

export interface TopicStat {
  id: string
  topic: string
  domain: string
  mastery: number
  answered: number
  accuracy: number
  recent_accuracy: number
  wrong_count: number
  last_reviewed_at?: string | null
}

export interface QuestionSummary {
  id: string
  domain: string
  topic: string
  concept: string
  difficulty: Difficulty
  type: QuestionType
  prompt: string
  verified: boolean
  bookmarked?: boolean
  question_style?: string
  quality_tier?: string
  source_kind?: string
  knowledge_points?: string[]
}

export interface KnowledgeCard {
  summary?: string
  why_it_matters?: string
  interview_angle?: string
  common_pitfall?: string
}

export interface ResultQuestion extends ExamQuestion {
  user_answer?: string | null
  correct_answer: string
  correct: boolean
  explanation: string
  distractor_explanations?: Record<string, string>
  attempt_count?: number
  historical_accuracy?: number
  takeaway?: string
  knowledge_card?: KnowledgeCard
  question_style?: string
  quality_tier?: string
}

export interface ExamResult {
  exam_id: string
  score: number
  total_score: number
  correct_count: number
  total_questions: number
  elapsed_seconds: number
  choice_accuracy: number
  fill_accuracy: number
  difficulty_breakdown: Record<string, number>
  topic_breakdown: Record<string, number>
  questions: ResultQuestion[]
  batch_id?: string | null
  paper_index?: number
  paper_count?: number
  next_exam_id?: string | null
}

export interface ProviderStatus {
  active_provider: string
  jev: 'connected' | 'not_configured' | 'error'
  nanojev: 'running' | 'offline'
  von: 'running' | 'offline'
}

export interface DrillQuestion extends ExamQuestion {
  position: number
  domain: string
  topic: string
  concept: string
  difficulty: Difficulty
  bookmarked?: boolean
}

export interface DrillFeedback {
  question_id: string
  correct: boolean
  is_correct: boolean
  correct_answer: string
  explanation: string
  distractor_explanations?: Record<string, string>
  takeaway?: string
  knowledge_card?: KnowledgeCard
  locale?: Locale
}

export interface DrillSummary {
  id: string
  answered: number
  correct: number
  status: 'finished'
}

export interface ImportIssue {
  line?: number
  message: string
  code?: string
}

export interface QuestionImportPreview {
  valid_count: number
  invalid_count: number
  duplicate_count: number
  errors: ImportIssue[]
}

export interface QuestionImportResult {
  imported_count: number
  skipped_count: number
  errors?: ImportIssue[]
}
