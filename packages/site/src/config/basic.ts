import React from 'react'

// 页面路由配置 - 唯一配置源
export interface PageRoute {
  name: string
  path: string
  label: string
  icon: string
  component: React.LazyExoticComponent<React.FC>
}

export const PAGE_ROUTES: PageRoute[] = [
  { name: 'Main', path: '/main', label: '首页', icon: 'Home', component: React.lazy(() => import('@pages/main')) },
  { name: 'AgentWorkbench', path: '/agent-workbench', label: '工作台', icon: 'LayoutDashboard', component: React.lazy(() => import('@pages/agent-workbench')) },
  { name: 'Money', path: '/money', label: '财务', icon: 'Wallet', component: React.lazy(() => import('@pages/money')) },
  { name: 'Health', path: '/health', label: '健康', icon: 'Heart', component: React.lazy(() => import('@pages/health')) },
  { name: 'Project', path: '/project', label: '项目', icon: 'FolderKanban', component: React.lazy(() => import('@pages/project')) },
  { name: 'Info', path: '/info', label: '资讯', icon: 'FileText', component: React.lazy(() => import('@pages/info')) },
  { name: 'Text', path: '/text', label: '文本', icon: 'Type', component: React.lazy(() => import('@pages/text')) },
  { name: 'Analysis', path: '/analysis', label: '分析', icon: 'BookOpen', component: React.lazy(() => import('@pages/analysis')) },
  { name: 'Necessity', path: '/necessity', label: '物资', icon: 'Package', component: React.lazy(() => import('@pages/necessity')) },
  { name: 'FileStorage', path: '/file-storage', label: '文件存储', icon: 'HardDrive', component: React.lazy(() => import('@pages/file_storage')) },
  { name: 'DAGPipeline', path: '/dag-pipeline', label: 'DAG流程', icon: 'GitBranch', component: React.lazy(() => import('@pages/dag_pipeline')) },
]

// 通过路径查找组件
export const getPageComponent = (path: string): React.LazyExoticComponent<React.FC> | undefined => {
  return PAGE_ROUTES.find(route => route.path === path)?.component
}
