import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { ExamBuilderPage } from './pages/ExamBuilderPage'
import { ExamPage } from './pages/ExamPage'
import { LearningMapPage } from './pages/LearningMapPage'
import { QuestionBankPage } from './pages/QuestionBankPage'
import { RapidDrillPage } from './pages/RapidDrillPage'
import { ResultPage } from './pages/ResultPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { SettingsPage } from './pages/SettingsPage'

export default function App(){return <Routes><Route element={<AppShell/>}><Route path="/" element={<DashboardPage/>}/><Route path="/exams/new" element={<ExamBuilderPage/>}/><Route path="/result/:id" element={<ResultPage/>}/><Route path="/drill" element={<RapidDrillPage/>}/><Route path="/learning-map" element={<LearningMapPage/>}/><Route path="/questions" element={<QuestionBankPage/>}/><Route path="/review" element={<ReviewQueuePage/>}/><Route path="/settings" element={<SettingsPage/>}/></Route><Route path="/exam/:id" element={<ExamPage/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}
