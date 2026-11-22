import { MAIN_ROUTES, PAGE_ROUTES, SYSTEM_ROUTES } from './basic'

describe('PAGE_ROUTES navigation integrity', () => {
  it('ensures every route has a unique path/name and a valid icon component', () => {
    const paths = new Set<string>()
    const names = new Set<string>()

    for (const route of PAGE_ROUTES) {
      expect(route.path.startsWith('/')).toBe(true)
      expect(route.label.trim().length).toBeGreaterThan(0)
      expect(route.icon).toBeDefined()
      expect(['function', 'object']).toContain(typeof route.icon)
      expect(paths.has(route.path)).toBe(false)
      expect(names.has(route.name)).toBe(false)
      paths.add(route.path)
      names.add(route.name)
    }
  })

  it('includes SailTick Coach in main routes and Trace Debug in bottom system routes', () => {
    const tick = MAIN_ROUTES.find((r) => r.path === '/tick')
    expect(tick).toBeDefined()
    expect(tick?.icon).toBeDefined()

    const traceDebug = SYSTEM_ROUTES.find((r) => r.path === '/trace-debug')
    expect(traceDebug).toBeDefined()
    expect(traceDebug?.icon).toBeDefined()
  })
})
