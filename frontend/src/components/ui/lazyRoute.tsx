import { lazy, Suspense, type ComponentType, type ReactNode } from 'react'

import RouteFallback from './RouteFallback'

/**
 * A route element whose code is only downloaded when the route is first visited, which keeps
 * the first page load small. The fallback appears inside the surrounding layout.
 */
export function lazyElement(load: () => Promise<{ default: ComponentType }>, fallback: ReactNode = <RouteFallback />) {
  const Page = lazy(load)
  return (
    <Suspense fallback={fallback}>
      <Page />
    </Suspense>
  )
}
