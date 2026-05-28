import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'
import WelcomePage from './pages/WelcomePage'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import MultiAgentPage from './pages/MultiAgentPage'
import AutomationsPage from './pages/AutomationsPage'

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
              <Route path="/automations" element={<AutomationsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </ErrorBoundary>
        </Layout>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
