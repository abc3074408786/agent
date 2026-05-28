<template>
  <div class="conversation-panel">
    <!-- 消息区域 -->
    <div class="messages" ref="messagesEl">
      <!-- 空状态 -->
      <div v-if="store.messages.length === 0" class="empty-state">
        <div class="empty-icon">💬</div>
        <p>输入你的开发需求，Leader 会自动分解并分配给团队</p>
        <p class="hint">例如: "开发一个用户注册功能，要有邮箱验证"</p>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="msg in store.messages"
        :key="msg.id"
        class="msg"
        :class="msg.role"
      >
        <div class="msg-header">
          <span v-if="msg.sender">{{ msg.sender }}</span>
          <span v-else-if="msg.role === 'user'">你</span>
        </div>
        <div class="msg-body" v-html="renderContent(msg.content)"></div>
      </div>

      <!-- 执行中指示器 -->
      <div v-if="store.isExecuting && runningTask" class="progress-indicator">
        <div class="spinner"></div>
        <span>{{ runningTask.role_icon }} {{ runningTask.title }}</span>
        <span class="model-hint">({{ runningTask.model }})</span>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <div class="input-row">
        <input
          ref="inputEl"
          v-model="inputText"
          type="text"
          placeholder="对 Leader 说话..."
          :disabled="store.isExecuting"
          @keydown.enter.prevent="send"
          autocomplete="off"
        />
        <button
          v-if="!store.isExecuting"
          class="btn-send"
          :disabled="!inputText.trim()"
          @click="send"
        >
          发送
        </button>
        <button
          v-else
          class="btn-cancel"
          @click="store.cancelExecution()"
        >
          取消
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useTeamStore } from '../stores/team'

const store = useTeamStore()
const inputText = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)

const runningTask = computed(() => {
  return store.tasks.find(t => t.status === 'running') || null
})

// 自动滚动到底部
watch(() => store.messages.length, () => {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
})

function send() {
  const text = inputText.value.trim()
  if (!text || store.isExecuting) return
  store.sendMessage(text)
  inputText.value = ''
}

function renderContent(text: string): string {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g,
    '<pre><code>$2</code></pre>')
  html = html.replace(/```([\s\S]*?)```/g,
    '<pre><code>$1</code></pre>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  // Tables (simple)
  html = html.replace(/\|(.+)\|/g, (match) => {
    if (match.includes('---')) return ''
    const cells = match.split('|').filter(c => c.trim())
    return '<div class="table-row">' +
      cells.map(c => `<span class="table-cell">${c.trim()}</span>`).join('') +
      '</div>'
  })
  // Newlines
  html = html.replace(/\n/g, '<br>')
  return html
}
</script>

<style scoped>
.conversation-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 消息区域 */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  gap: 8px;
}

.empty-icon { font-size: 40px; opacity: 0.5; }
.empty-state p { font-size: 13px; }
.hint { font-size: 11px !important; opacity: 0.7; margin-top: 2px; }

/* 消息 */
.msg {
  margin-bottom: 14px;
  max-width: 88%;
  animation: fadeIn 0.25s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg.user { margin-left: auto; }

.msg-header {
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 3px;
  padding-left: 2px;
}

.msg.user .msg-header { text-align: right; padding-right: 2px; }

.msg-body {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.65;
  word-break: break-word;
}

.msg.user .msg-body {
  background: var(--accent);
  color: #1a1b26;
  border-bottom-right-radius: 3px;
}

.msg.leader .msg-body {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-bottom-left-radius: 3px;
}

.msg.agent .msg-body {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-bottom-left-radius: 3px;
}

.msg.system .msg-body {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  text-align: center;
  font-size: 11px;
}

.msg-body :deep(pre) {
  background: var(--bg-primary);
  padding: 8px 10px;
  border-radius: 5px;
  margin: 6px 0;
  overflow-x: auto;
  font-size: 11px;
  line-height: 1.5;
}

.msg-body :deep(code) {
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 11px;
}

.msg-body :deep(h3), .msg-body :deep(h4) {
  margin: 8px 0 4px;
  font-size: 12px;
  color: var(--accent);
}

.msg-body :deep(.table-row) {
  display: flex;
  gap: 4px;
  padding: 2px 0;
  font-size: 11px;
}

.msg-body :deep(.table-cell) {
  padding: 2px 6px;
  background: var(--bg-primary);
  border-radius: 3px;
  flex: 1;
}

.msg-body :deep(strong) { color: var(--accent); }

/* 进度指示器 */
.progress-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: 8px;
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 8px;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.model-hint { opacity: 0.5; font-size: 10px; }

/* 输入区 */
.input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
}

.input-row {
  display: flex;
  gap: 8px;
}

.input-row input {
  flex: 1;
  padding: 9px 12px;
  border-radius: 7px;
  border: 1px solid var(--border);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.input-row input:focus { border-color: var(--accent); }
.input-row input::placeholder { color: var(--text-muted); }
.input-row input:disabled { opacity: 0.5; }

.btn-send, .btn-cancel {
  padding: 9px 16px;
  border-radius: 7px;
  border: none;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-send {
  background: var(--accent);
  color: #1a1b26;
}

.btn-send:hover { opacity: 0.85; }
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-cancel {
  background: var(--accent-red);
  color: #fff;
}

.btn-cancel:hover { opacity: 0.85; }
</style>
