import type { RouteObject } from 'react-router'

import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import LandingPage from './pages/LandingPage'
import NotFoundPage from './pages/NotFoundPage'

// Kept separate from App so tests can mount the same routes in a memory router.
export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  {
    element: <AppLayout />,
    children: [{ path: '/dashboard', element: <DashboardPage /> }],
  },
  { path: '*', element: <NotFoundPage /> },
]
