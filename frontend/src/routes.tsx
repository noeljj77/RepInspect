import type { RouteObject } from 'react-router'

import { GuestOnly, RequireAuth } from './components/auth/RouteGuards'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import RegisterPage from './pages/RegisterPage'
import RepositoryPage from './pages/RepositoryPage'
import DependenciesTab from './pages/repository/DependenciesTab'
import FilesTab from './pages/repository/FilesTab'
import OverviewTab from './pages/repository/OverviewTab'

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
          { path: '/dashboard', element: <DashboardPage /> },
          {
            path: '/repositories/:repositoryId',
            element: <RepositoryPage />,
            children: [
              { index: true, element: <OverviewTab /> },
              { path: 'files', element: <FilesTab /> },
              { path: 'dependencies', element: <DependenciesTab /> },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]
