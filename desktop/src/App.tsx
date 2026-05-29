import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'
import ToastContainer from './components/Toast'
import CommandPalette from './components/CommandPalette'
import WelcomePage from './pages/WelcomePage'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import MultiAgentPage from './pages/MultiAgentPage'
import AutomationsPage from './pages/AutomationsPage'
import TeamDevPage from './pages/TeamDevPage'
import ExpertMarketplace from './pages/ExpertMarketplace'
import SkillLibrary from './pages/SkillLibrary'
import WorkflowList from './pages/WorkflowList'
import WorkflowEditor from './pages/WorkflowEditor'

export default function App() {
  return (
    <ErrorBoundary fallbackTitle="应用出现了问题">
      <BrowserRouter>
        <Layout>
          <ErrorBoundary fallbackTitle="页面加载失败">
            <Routes>
              <Route path="/" element={<WelcomePage />} />
              <Route path="/chat/:sessionId" element={<ChatPage />} />
              <Route path="/agents" element={<MultiAgentPage />} />
              <Route path="/team" element={<TeamDevPage />} />
              <Route path="/experts" element={<ExpertMarketplace />} />
              <Route path="/skills" element={<SkillLibrary />} />
              <Route path="/workflows" element={<WorkflowList />} />
              <Route path="/workflows/new" element={<WorkflowEditor />} />
              <Route path="/workflows/:id" element={<WorkflowEditor />} />
              <Route path="/automations" element={<AutomationsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </ErrorBoundary>
        </Layout>
        <ToastContainer />
        <CommandPalette />
      </BrowserRouter>
    </ErrorBoundary>
  )
}
