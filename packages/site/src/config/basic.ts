export const PAGE_ROUTES = [
  { name: 'Home', path: '/', label: '首页', icon: 'Home' },
  { name: 'Money', path: '/money', label: '财务', icon: 'Wallet' },
  { name: 'Health', path: '/health', label: '健康', icon: 'Heart' },
  { name: 'Project', path: '/project', label: '项目', icon: 'FolderKanban' },
  { name: 'Content', path: '/content', label: '内容', icon: 'FileText' },
  { name: 'Text', path: '/text', label: '文本', icon: 'Type' },
  { name: 'Analysis', path: '/analysis', label: '分析', icon: 'BookOpen' },
  { name: 'Necessity', path: '/necessity', label: '物资', icon: 'Package' },
]

export type PageRoute = (typeof PAGE_ROUTES)[number]