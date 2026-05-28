<template>
  <aside class="task-panel">
    <!-- 面板标题 -->
    <div class="panel-header">
      <span>任务面板</span>
      <span v-if="store.totalCount > 0" class="count">
        {{ store.completedCount }}/{{ store.totalCount }}
      </span>
    </div>

    <!-- Leader 卡片 -->
    <div class="leader-card">
      <div class="leader-title">
        <span>🎯</span>
        <span>Leader</span>
      </div>
      <div class="leader-status" :class="{ active: store.status === 'planning' }">
        {{ leaderStatusText }}
      </div>
    </div>

    <!-- 子任务分隔线 -->
    <div v-if="store.tasks.length > 0" class="section-divider">
      <span>子任务</span>
    </div>

    <!-- 子任务列表 -->
    <div class="task-list">
      <div
        v-for="task in store.tasks"
        :key="task.id"
        class="task-item"
        :class="{ active: selectedTaskId === task.id }"
        @click="selectedTaskId = task.id"
      >
        <div class="task-header">
          <span class="status-icon" :class="`status-${task.status}`">
            {{ statusIcon(task.status) }}
          </span>
          <span class="task-title">{{ task.title }}</span>
        </div>
        <div class="task-meta">
          <span class="role-dot" :style="{ background: task.role_color }"></span>
          <span>{{ task.role_icon }} {{ task.role_label }}</span>
          <span class="model-tag">{{ task.model }}</span>
        </div>
        <!-- 运行中动画 -->
        <div v-if="task.status === 'running'" class="running-bar">
          <div class="running-bar-fill"></div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="store.tasks.length === 0" class="empty-state">
        <div class="empty-icon">📋</div>
        <p>发送消息开始任务</p>
      </div>
    </div>

    <!-- 底部服务器状态 -->
    <div class="panel-footer">
      <div class="server-info">
        <span class="server-dot-sm" :class="serverDotClass"></span>
        <span>{{ serverLabel }}</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTeamStore } from '../stores/team'

const store = useTeamStore()
const selectedTaskId = ref<string | null>(null)

const leaderStatusText = computed(() => {
  switch (store.status) {
    case 'planning': return '正在拆解任务...'
    case 'executing': return `执行中 (${store.completedCount}/${store.totalCount})`
    case 'completed': return '✅ 全部完成'
    case 'error': return '❌ 出错'
    case 'cancelled': return '⛔ 已取消'
    default: return '等待指令...'
  }
})

const serverDotClass = computed(() => ({
  'dot-sm-green': store.serverStatus === 'running',
  'dot-sm-yellow': store.serverStatus === 'starting',
  'dot-sm-red': store.serverStatus === 'stopped' || store.serverStatus === 'error',
}))

const serverLabel = computed(() => {
  if (store.serverStatus === 'running') return `localhost:${store.serverPort}`
  if (store.serverStatus === 'starting') return '启动中...'
  return '未连接'
})

function statusIcon(status: string): string {
  const icons: Record<string, string> = {
    pending: '⏳',
    running: '🔄',
    completed: '✓',
    failed: '✗',
  }
  return icons[status] || '⏳'
}
</script>

<style scoped>
.task-panel {
  width: 280px;
  min-width: 280px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.count {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--bg-tertiary);
  color: var(--accent-green);
}

/* Leader 卡片 */
.leader-card {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  background: rgba(122,162,247,0.03);
}

.leader-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.leader-status {
  font-size: 11px;
  color: var(--text-muted);
  transition: color 0.2s;
}

.leader-status.active {
  color: var(--accent-yellow);
}

/* 分隔线 */
.section-divider {
  padding: 8px 14px 4px;
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

/* 任务列表 */
.task-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.task-item {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(59,66,97,0.4);
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}

.task-item:hover { background: var(--bg-tertiary); }
.task-item.active { background: rgba(122,162,247,0.08); border-left: 3px solid var(--accent); }

.task-header {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 4px;
}

.status-icon {
  font-size: 12px;
  width: 18px;
  text-align: center;
}

.status-pending { color: var(--text-muted); }
.status-running { color: var(--accent-yellow); animation: spin 1.5s linear infinite; }
.status-completed { color: var(--accent-green); font-weight: bold; }
.status-failed { color: var(--accent-red); font-weight: bold; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.task-title {
  font-size: 12px;
  font-weight: 500;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: var(--text-muted);
  margin-left: 25px;
}

.role-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.model-tag {
  padding: 0 4px;
  border-radius: 3px;
  background: var(--bg-tertiary);
  font-family: monospace;
  font-size: 9px;
}

/* 运行中进度条 */
.running-bar {
  height: 2px;
  background: var(--bg-tertiary);
  border-radius: 1px;
  margin-top: 6px;
  margin-left: 25px;
  overflow: hidden;
}

.running-bar-fill {
  height: 100%;
  width: 40%;
  background: var(--accent-yellow);
  border-radius: 1px;
  animation: progress-slide 1.5s ease-in-out infinite;
}

@keyframes progress-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(300%); }
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
  gap: 8px;
}

.empty-icon { font-size: 32px; opacity: 0.5; }
.empty-state p { font-size: 12px; }

/* 底部 */
.panel-footer {
  padding: 8px 14px;
  border-top: 1px solid var(--border);
  font-size: 10px;
  color: var(--text-muted);
}

.server-info {
  display: flex;
  align-items: center;
  gap: 5px;
}

.server-dot-sm {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}

.dot-sm-green { background: var(--accent-green); }
.dot-sm-yellow { background: var(--accent-yellow); }
.dot-sm-red { background: var(--accent-red); }
</style>
