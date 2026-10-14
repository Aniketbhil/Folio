import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { OverviewPage } from '../pages/OverviewPage'
import { StudentsPage } from '../pages/StudentsPage'
import { CoursesPage } from '../pages/CoursesPage'
import { SourcesPage } from '../pages/SourcesPage'
import { TutorPage } from '../pages/TutorPage'
import { AssessmentsPage } from '../pages/AssessmentsPage'
import { MasteryPage } from '../pages/MasteryPage'
import { NotFoundPage } from '../pages/NotFoundPage'

export const AppRouter: React.FC = () => {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/students" element={<StudentsPage />} />
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/tutor" element={<TutorPage />} />
        <Route path="/assessments" element={<AssessmentsPage />} />
        <Route path="/mastery" element={<MasteryPage />} />
        <Route path="/overview" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}
