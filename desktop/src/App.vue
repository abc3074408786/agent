<template>
  <div class="app">
    <!-- 标题栏 (可拖动) -->
    <header class="titlebar" @mousedown="dragWindow">
      <div class="titlebar-left">
        <span class="app-icon">🎯</span>
        <h1>标准开发组</h1>
      </div>
      <div class="titlebar-right">
        <span class="badge" :class="{ active: store.status !== 'idle' }">
          {{ statusLabel }}
        </span>
        <span class="badge">
          {{ store.sessionId ? `#${store.sessionId}` : '未连接' }}
        </span>
        <span class="server-dot" :class="serverStatusClass" :title="serverStatusTip"></span>
      </div>
    </header>

    <!-- 主布局 -->
    <main class="main-layout">
      <!-- 左侧任务面板 -->
      <TaskPanel />

      <!-- 右侧对话区 -->
      <ConversationPanel />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useTeamStore } from './stores/team'
import TaskPanel from './components/TaskPanel.vue'
import ConversationPanel from './components/ConversationPanel.vue'

const store = useTeamStore()

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    idle: '空闲',
    planning: '规划中',
    executing: '执行中',
    completed: '已完成',
    error: '出错',
    cancelled: '已取消',
  }
  return map[store.status] || store.status
})

const serverStatusClass = computed(() => ({
  'dot-green': store.serverStatus === 'running',
  'dot-yellow': store.serverStatus === 'starting',
  'dot-red': store.serverStatus === 'stopped' || store.serverStatus === 'error',
}))

const serverStatusTip = computed(() => {
  const map: Record<string, string> = {
    running: 'Python 后端运行中',
    starting: '启动中...',
    stopped: '后端未运行',
    error: '后端出错',
    'not-found': 'Python 脚本未找到',
  }
  return map[store.serverStatus] || ''
})

function dragWindow(e: MouseEvent) {
  // 原生标题栏拖动由 CSS -webkit-app-region 处理
}

let cleanupStatus: (() => void) | null = null
let cleanupLog: (() => void) | null = null

onMounted(async () => {
  // 监听 Python 后端状态
  if (window.electronAPI) {
    cleanupStatus = window.electronAPI.onPythonStatus((data) => {
      store.serverStatus = data.status
      if (data.port) store.serverPort = data.port
    })
    cleanupLog = window.electronAPI.onPythonLog((data) => {
      store.addLog(data.message, data.level || 'info')
    })

    // 获取服务器信息
    const info = await window.electronAPI.getServerInfo()
    store.serverPort = info.port
    if (info.isRunning) store.serverStatus = 'running'
  }

  // 自动连接 WebSocket
  store.connect()
})

onUnmounted(() => {
  cleanupStatus?.()
  cleanupLog?.()
  store.disconnect()
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg-primary: #1a1b26;
  --bg-secondary: #24283b;
  --bg-tertiary: #2f3549;
  --text-primary: #c0caf5;
  --text-secondary: #a9b1d6;
  --text-muted: #565f89;
  --accent: #7aa2f7;
  --accent-green: #9ece6a;
  --accent-yellow: #e0af68;
  --accent-red: #f7768e;
  --accent-purple: #bb9af7;
  --border: #3b4261;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  height: 100vh;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 标题栏 */
.titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  -webkit-app-region: drag;
  user-select: none;
}

.titlebar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.titlebar-left h1 {
  font-size: 14px;
  font-weight: 600;
}

.app-icon { font-size: 16px; }

.titlebar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  -webkit-app-region: no-drag;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.badge.active {
  background: rgba(122,162,247,0.15);
  color: var(--accent);
  border-color: var(--accent);
}

.server-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.dot-green { background: var(--accent-green); }
.dot-yellow { background: var(--accent-yellow); animation: pulse 1s infinite; }
.dot-red { background: var(--accent-red); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 主布局 */
.main-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 滚动条 */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
