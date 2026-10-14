import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { MetaProvider } from './context/MetaContext'
import { AuthProvider } from './context/AuthContext'
import { StudentProvider } from './context/StudentContext'
import { CourseProvider } from './context/CourseContext'
import { AppRouter } from './app/router'

export default function App() {
  return (
    <ThemeProvider>
      <MetaProvider>
        <AuthProvider>
          <StudentProvider>
            <CourseProvider>
              <BrowserRouter>
                <AppRouter />
              </BrowserRouter>
            </CourseProvider>
          </StudentProvider>
        </AuthProvider>
      </MetaProvider>
    </ThemeProvider>
  )
}
