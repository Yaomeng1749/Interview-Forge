import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Locale } from '../types'

const messages = {
  'zh-CN': {
    'app.name': '求职训练工场', 'app.kicker': 'MLE / SDE 考场控制台',
    'nav.dashboard': '控制台', 'nav.exam': '建卷', 'nav.drill': '快速练习', 'nav.map': '学习地图', 'nav.questions': '题库', 'nav.review': '复习队列', 'nav.settings': '设置',
    'action.start': '开始标准卷', 'action.four': '连续刷 4 套', 'action.custom': '专项组卷', 'action.wrong': '错题卷', 'action.retry': '重试', 'action.previous': '上一题', 'action.next': '下一题', 'action.flag': '标记', 'action.unflag': '取消标记', 'action.submit': '提前交卷', 'action.confirmSubmit': '确认交卷', 'action.resume': '继续考试',
    'status.loading': '正在读取本机训练数据…', 'status.empty': '暂无数据', 'status.saving': '保存中', 'status.saved': '已保存', 'status.saveFailed': '保存失败，答案已保留在本机', 'status.offline': '后端暂不可用',
    'exam.remaining': '剩余时间', 'exam.question': '题目', 'exam.unanswered': '未答', 'exam.answered': '已答', 'exam.flagged': '已标记', 'exam.timeup': '时间到，正在交卷…', 'exam.frozen': '本卷题目与语言已冻结',
    'dashboard.today': '今日进度', 'dashboard.accuracy': '今日正确率', 'dashboard.exams': '完成套卷', 'dashboard.time': '今日专注', 'dashboard.total': '累计作答', 'dashboard.mastery': '能力掌握度', 'dashboard.review': '待复习错题',
    'common.questions': '题', 'common.minutes': '分钟', 'common.page': '页', 'common.all': '全部',
    'result.yourAnswer': '你的答案', 'result.correctAnswer': '正确答案', 'result.explanation': '完整解析',
    'settings.provider': '决策引擎状态', 'settings.language': '界面语言', 'settings.goal': '每日目标题数', 'settings.secret': '密钥仅从后端环境变量读取，不会传入浏览器。',
    'error.inventory': '题库不足，无法按当前条件组卷。约束未被放宽。', 'error.generic': '请求失败，请检查本机 API 服务后重试。',
  },
  'en-US': {
    'app.name': 'Interview Forge', 'app.kicker': 'MLE / SDE exam operations',
    'nav.dashboard': 'Dashboard', 'nav.exam': 'Build Exam', 'nav.drill': 'Rapid Drill', 'nav.map': 'Learning Map', 'nav.questions': 'Question Bank', 'nav.review': 'Review Queue', 'nav.settings': 'Settings',
    'action.start': 'Start Standard Exam', 'action.four': 'Four-Exam Streak', 'action.custom': 'Custom Exam', 'action.wrong': 'Wrong-Answer Exam', 'action.retry': 'Retry', 'action.previous': 'Previous', 'action.next': 'Next', 'action.flag': 'Flag', 'action.unflag': 'Unflag', 'action.submit': 'Submit Early', 'action.confirmSubmit': 'Confirm Submission', 'action.resume': 'Resume Exam',
    'status.loading': 'Reading local training data…', 'status.empty': 'No data yet', 'status.saving': 'Saving', 'status.saved': 'Saved', 'status.saveFailed': 'Save failed — answer retained locally', 'status.offline': 'Backend unavailable',
    'exam.remaining': 'Time Remaining', 'exam.question': 'Question', 'exam.unanswered': 'Unanswered', 'exam.answered': 'Answered', 'exam.flagged': 'Flagged', 'exam.timeup': 'Time is up. Submitting…', 'exam.frozen': 'Questions and locale are frozen for this exam',
    'dashboard.today': 'Today', 'dashboard.accuracy': 'Accuracy', 'dashboard.exams': 'Exams Complete', 'dashboard.time': 'Focus Time', 'dashboard.total': 'Lifetime Answers', 'dashboard.mastery': 'Mastery', 'dashboard.review': 'Review Due',
    'common.questions': 'questions', 'common.minutes': 'minutes', 'common.page': 'page', 'common.all': 'All',
    'result.yourAnswer': 'Your Answer', 'result.correctAnswer': 'Correct Answer', 'result.explanation': 'Explanation',
    'settings.provider': 'Decision Provider Status', 'settings.language': 'Interface Language', 'settings.goal': 'Daily Question Goal', 'settings.secret': 'Provider keys are read by the backend environment only and never enter this browser.',
    'error.inventory': 'Not enough questions for these constraints. No constraint was relaxed.', 'error.generic': 'Request failed. Check the local API service and retry.',
  },
} as const

type MessageKey = keyof typeof messages['zh-CN']
interface LocaleContextValue { locale: Locale; setLocale: (locale: Locale) => void; t: (key: MessageKey) => string }
const LocaleContext = createContext<LocaleContextValue | null>(null)

export function LocaleProvider({ children }: { children: ReactNode }) {
  const initial = localStorage.getItem('exam:locale') === 'en-US' ? 'en-US' : 'zh-CN'
  const [locale, updateLocale] = useState<Locale>(initial)
  const value = useMemo<LocaleContextValue>(() => ({
    locale,
    setLocale(next) { localStorage.setItem('exam:locale', next); updateLocale(next) },
    t: (key) => messages[locale][key],
  }), [locale])
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useI18n() {
  const value = useContext(LocaleContext)
  if (!value) throw new Error('useI18n must be used inside LocaleProvider')
  return value
}

export function LocaleToggle() {
  const { locale, setLocale } = useI18n()
  return <div className="locale-toggle" role="group" aria-label="Language / 语言">
    <button aria-pressed={locale === 'zh-CN'} onClick={() => setLocale('zh-CN')}>中文</button>
    <button aria-pressed={locale === 'en-US'} aria-label="English" onClick={() => setLocale('en-US')}>EN</button>
  </div>
}
