import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import TitleBar from './TitleBar'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex flex-col h-screen w-screen bg-white">
      {/* 标题栏 */}
      <TitleBar />

      {/* 主体 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左侧边栏 */}
        <Sidebar />

        {/* 主内容区 */}
        <main className="flex-1 overflow-hidden bg-white">
          {children}
        </main>
      </div>
    </div>
  )
}
