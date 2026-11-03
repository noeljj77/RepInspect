import type { RouteObject } from 'react-router'

import { GuestOnly, RequireAuth } from './components/auth/RouteGuards'
import AppLayout from './components/layout/AppLayout'
import { lazyElement } from './components/ui/lazyRoute'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import RegisterPage from './pages/RegisterPage'

// Kept separate from App so tests can mount the same routes in a memory router.
export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  {
    element: <GuestOnly />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
    ],
  },
  {
    // Everything inside the app shell needs a logged-in user.
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/dashboard', element: lazyElement(() => import('./pages/DashboardPage')) },
          {
            path: '/repositories/:repositoryId',
            element: lazyElement(() => import('./pages/RepositoryPage')),
            children: [
              { index: true, element: lazyElement(() => import('./pages/repository/OverviewTab')) },
              { path: 'files', element: lazyElement(() => import('./pages/repository/FilesTab')) },
              { path: 'dependencies', element: lazyElement(() => import('./pages/repository/DependenciesTab')) },
              { path: 'chat', element: lazyElement(() => import('./pages/repository/ChatTab')) },
              { path: 'interview', element: lazyElement(() => import('./pages/repository/InterviewTab')) },
              { path: 'interview/mock/:interviewId', element: lazyElement(() => import('./pages/repository/MockInterviewPage')) },
              { path: 'notes', element: lazyElement(() => import('./pages/repository/NotesTab')) },
              { path: 'history', element: lazyElement(() => import('./pages/repository/HistoryTab')) },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]
