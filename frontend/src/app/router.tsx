import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { PublicRoute } from '../components/auth/PublicRoute'
import { ProtectedRoute } from '../components/auth/ProtectedRoute'
import { LandingPage } from '../pages/LandingPage'
import { LoginPage } from '../pages/LoginPage'
import { RegisterPage } from '../pages/RegisterPage'
import { OverviewPage } from '../pages/OverviewPage'
import { ProfilePage } from '../pages/ProfilePage'
import { CoursesPage } from '../pages/CoursesPage'
import { SourcesPage } from '../pages/SourcesPage'
import { TutorPage } from '../pages/TutorPage'
import { AssessmentsPage } from '../pages/AssessmentsPage'
import { MasteryPage } from '../pages/MasteryPage'
import { NotFoundPage } from '../pages/NotFoundPage'

export const AppRouter: React.FC = () => {
  return (
    <Routes>
      {/* Public Landing & Marketing */}
      <Route path="/" element={<LandingPage />} />

      {/* Public Auth Routes (Redirect to /overview if already authenticated) */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        }
      />

      {/* Protected Workspace Routes (Rendered inside AppShell by ProtectedRoute) */}
      <Route
        path="/overview"
        element={
          <ProtectedRoute>
            <OverviewPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/courses"
        element={
          <ProtectedRoute>
            <CoursesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sources"
        element={
          <ProtectedRoute>
            <SourcesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tutor"
        element={
          <ProtectedRoute>
            <TutorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assessments"
        element={
          <ProtectedRoute>
            <AssessmentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mastery"
        element={
          <ProtectedRoute>
            <MasteryPage />
          </ProtectedRoute>
        }
      />

      {/* Backward Compatibility & Fallback Redirects */}
      <Route path="/students" element={<Navigate to="/profile" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
