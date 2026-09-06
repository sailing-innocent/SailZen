import * as React from "react"

const MOBILE_BREAKPOINT = 768

// 创建 Context 共享移动端状态
const MobileContext = React.createContext<boolean>(false)

/**
 * MobileProvider - 全局移动端状态提供者
 * 
 * 性能优化：使用单一的 MediaQuery 监听器，通过 Context 共享状态，
 * 避免每个使用 useIsMobile 的组件都创建独立的监听器。
 */
export function MobileProvider({ children }: { children: React.ReactNode }) {
  const [isMobile, setIsMobile] = React.useState(() => {
    // SSR 安全的初始值
    if (typeof window === 'undefined') return false
    return window.innerWidth < MOBILE_BREAKPOINT
  })

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    
    // 初始化
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    
    // 监听变化
    mql.addEventListener("change", onChange)
    
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return (
    <MobileContext.Provider value={isMobile}>
      {children}
    </MobileContext.Provider>
  )
}

/**
 * useIsMobile - 获取当前是否为移动端
 * 
 * 优先使用 Context 中的共享状态，如果未被 MobileProvider 包裹则降级使用本地状态。
 */
export function useIsMobile(): boolean {
  // 尝试从 Context 获取
  const contextValue = React.useContext(MobileContext)
  
  // 检查是否在 Provider 内部（通过检查是否有父级 Provider）
  // 由于默认值是 false，我们需要一种方式来判断是否真正在 Provider 内
  // 这里我们用一个额外的 Context 来标记
  const hasProvider = React.useContext(MobileProviderExistsContext)
  
  // 本地状态作为降级方案
  const [localIsMobile, setLocalIsMobile] = React.useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth < MOBILE_BREAKPOINT
  })

  React.useEffect(() => {
    // 如果已有 Provider，不需要本地监听
    if (hasProvider) return

    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => {
      setLocalIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    mql.addEventListener("change", onChange)
    setLocalIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    return () => mql.removeEventListener("change", onChange)
  }, [hasProvider])

  return hasProvider ? contextValue : localIsMobile
}

// 用于标记是否存在 Provider 的 Context
const MobileProviderExistsContext = React.createContext<boolean>(false)

/**
 * 完整的 MobileProvider，包含存在性标记
 */
export function MobileProviderWithFallback({ children }: { children: React.ReactNode }) {
  const [isMobile, setIsMobile] = React.useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth < MOBILE_BREAKPOINT
  })

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    mql.addEventListener("change", onChange)
    
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return (
    <MobileProviderExistsContext.Provider value={true}>
      <MobileContext.Provider value={isMobile}>
        {children}
      </MobileContext.Provider>
    </MobileProviderExistsContext.Provider>
  )
}

// 导出 MOBILE_BREAKPOINT 供其他地方使用
export { MOBILE_BREAKPOINT }
