"""
Frontend HTML - 单文件前端

匹配 UI Mockup:
- 左侧: 任务面板 (Leader + 子任务列表)
- 右侧: 对话区 + 任务详情输出
"""


def get_html() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>标准开发组 - 团队协作面板</title>
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
    --shadow: rgba(0,0,0,0.3);
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    height: 100vh;
    overflow: hidden;
}

/* ============ 顶部标题栏 ============ */
.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
}

.header h1 {
    font-size: 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}

.header .badges {
    display: flex;
    gap: 8px;
}

.badge {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 10px;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: 1px solid var(--border);
}

.badge.active { background: rgba(122,162,247,0.15); color: var(--accent); border-color: var(--accent); }

/* ============ 主布局 ============ */
.main {
    display: flex;
    height: calc(100vh - 49px);
}

/* ============ 左侧任务面板 ============ */
.sidebar {
    width: 300px;
    min-width: 300px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
}

.sidebar-header {
    padding: 14px 16px;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.leader-card {
    padding: 14px 16px;
    border-bottom: 1px solid var(--border);
    background: rgba(122,162,247,0.05);
}

.leader-card .leader-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 6px;
}

.leader-card .leader-status {
    font-size: 12px;
    color: var(--text-muted);
}

.leader-card .leader-status.active {
    color: var(--accent-yellow);
}

/* 子任务列表 */
.task-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
}

.task-item {
    padding: 12px 16px;
    border-bottom: 1px solid rgba(59,66,97,0.5);
    cursor: pointer;
    transition: background 0.15s;
}

.task-item:hover { background: var(--bg-tertiary); }
.task-item.active { background: rgba(122,162,247,0.1); border-left: 3px solid var(--accent); }

.task-item .task-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.task-item .task-status-icon {
    font-size: 14px;
    width: 20px;
    text-align: center;
}

.task-item .task-title {
    font-size: 13px;
    font-weight: 500;
    flex: 1;
}

.task-item .task-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-muted);
    margin-left: 28px;
}

.task-item .task-model {
    padding: 1px 5px;
    border-radius: 3px;
    background: var(--bg-tertiary);
    font-family: monospace;
    font-size: 10px;
}

.task-item .task-role-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

/* 状态颜色 */
.status-pending { color: var(--text-muted); }
.status-running { color: var(--accent-yellow); }
.status-completed { color: var(--accent-green); }
.status-failed { color: var(--accent-red); }

/* ============ 右侧内容区 ============ */
.content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* 对话区 */
.conversation {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.msg {
    margin-bottom: 16px;
    max-width: 90%;
    animation: fadeIn 0.3s;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

.msg.user {
    margin-left: auto;
}

.msg .msg-header {
    font-size: 11px;
    color: var(--text-muted);
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.msg .msg-body {
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.6;
}

.msg.user .msg-body {
    background: var(--accent);
    color: #1a1b26;
    border-bottom-right-radius: 4px;
}

.msg.leader .msg-body {
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-bottom-left-radius: 4px;
}

.msg.agent .msg-body {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-bottom-left-radius: 4px;
}

.msg .msg-body pre {
    background: var(--bg-primary);
    padding: 10px 12px;
    border-radius: 6px;
    margin: 8px 0;
    overflow-x: auto;
    font-size: 12px;
    line-height: 1.5;
}

.msg .msg-body code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px;
}

/* 进度指示器 */
.progress-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 12px;
}

.progress-indicator .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.progress-bar {
    height: 3px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    margin-top: 6px;
    overflow: hidden;
}

.progress-bar .fill {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.3s;
}

/* ============ 输入区 ============ */
.input-area {
    padding: 16px 20px;
    border-top: 1px solid var(--border);
    background: var(--bg-secondary);
}

.input-row {
    display: flex;
    gap: 10px;
}

.input-row input {
    flex: 1;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 13px;
    outline: none;
    transition: border-color 0.2s;
}

.input-row input:focus { border-color: var(--accent); }
.input-row input::placeholder { color: var(--text-muted); }

.input-row button {
    padding: 10px 20px;
    border-radius: 8px;
    border: none;
    background: var(--accent);
    color: #1a1b26;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s;
}

.input-row button:hover { opacity: 0.85; }
.input-row button:disabled { opacity: 0.4; cursor: not-allowed; }

/* ============ 空状态 ============ */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    gap: 12px;
}

.empty-state .icon { font-size: 48px; opacity: 0.5; }
.empty-state p { font-size: 14px; }

/* ============ 滚动条 ============ */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
</head>
<body>

<!-- 标题栏 -->
<div class="header">
    <h1>🎯 标准开发组</h1>
    <div class="badges">
        <span class="badge" id="badge-status">空闲</span>
        <span class="badge" id="badge-session"></span>
    </div>
</div>

<!-- 主布局 -->
<div class="main">
    <!-- 左侧任务面板 -->
    <div class="sidebar">
        <div class="sidebar-header">任务面板</div>

        <!-- Leader 卡片 -->
        <div class="leader-card">
            <div class="leader-title">🎯 Leader</div>
            <div class="leader-status" id="leader-status">等待指令...</div>
        </div>

        <!-- 子任务列表 -->
        <div class="task-list" id="task-list">
            <div class="empty-state" id="task-empty">
                <div class="icon">📋</div>
                <p>发送消息开始任务</p>
            </div>
        </div>
    </div>

    <!-- 右侧内容区 -->
    <div class="content">
        <!-- 对话区 -->
        <div class="conversation" id="conversation">
            <div class="empty-state" id="conv-empty">
                <div class="icon">💬</div>
                <p>输入你的开发需求，Leader 会自动分解并分配给团队</p>
                <p style="font-size:12px; margin-top:4px;">例如: "开发一个用户注册功能，要有邮箱验证"</p>
            </div>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
            <div class="input-row">
                <input
                    type="text"
                    id="message-input"
                    placeholder="对 Leader 说话..."
                    autocomplete="off"
                />
                <button id="send-btn" onclick="sendMessage()">发送</button>
            </div>
        </div>
    </div>
</div>

<script>
// ============ 状态 ============
let ws = null;
let sessionId = null;
let tasks = {};
let isExecuting = false;

// ============ 初始化 ============
async function init() {
    // 创建会话
    const res = await fetch('/api/sessions', { method: 'POST' });
    const data = await res.json();
    sessionId = data.session_id;
    document.getElementById('badge-session').textContent = `#${sessionId}`;

    // 连接 WebSocket
    connectWS();
}

function connectWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/${sessionId}`);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (e) => {
        const event = JSON.parse(e.data);
        handleEvent(event);
    };

    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting...');
        setTimeout(connectWS, 2000);
    };

    ws.onerror = (e) => {
        console.error('WebSocket error', e);
    };
}

// ============ 事件处理 ============
function handleEvent(event) {
    switch (event.type) {
        case 'connected':
            break;

        case 'status':
            updateStatus(event.status, event.message);
            break;

        case 'plan':
            handlePlan(event.plan, event.message);
            break;

        case 'task_started':
            handleTaskStarted(event);
            break;

        case 'task_progress':
            handleTaskProgress(event);
            break;

        case 'task_completed':
            handleTaskCompleted(event);
            break;

        case 'task_failed':
            handleTaskFailed(event);
            break;

        case 'all_completed':
            handleAllCompleted(event);
            break;

        case 'error':
            addMessage('system', `❌ ${event.message}`, 'leader');
            setExecuting(false);
            break;

        case 'cancelled':
            addMessage('system', `⛔ ${event.message}`, 'leader');
            setExecuting(false);
            break;

        case 'pong':
            break;
    }
}

function updateStatus(status, message) {
    const badge = document.getElementById('badge-status');
    const leader = document.getElementById('leader-status');

    leader.textContent = message;

    if (status === 'planning') {
        badge.textContent = '规划中';
        badge.className = 'badge active';
        leader.className = 'leader-status active';
    } else if (status === 'executing') {
        badge.textContent = '执行中';
        badge.className = 'badge active';
    } else if (status === 'completed') {
        badge.textContent = '已完成';
        badge.className = 'badge';
        leader.className = 'leader-status';
        setExecuting(false);
    }
}

function handlePlan(plan, message) {
    // 清除空状态
    document.getElementById('task-empty')?.remove();

    // Leader 消息
    addMessage('leader', plan.summary, 'leader');

    // 更新任务面板
    const taskList = document.getElementById('task-list');
    taskList.innerHTML = '';

    plan.subtasks.forEach((st) => {
        tasks[st.id] = st;
        const el = createTaskElement(st);
        taskList.appendChild(el);
    });

    document.getElementById('leader-status').textContent = `已分解 ${plan.subtasks.length} 个子任务`;
}

function handleTaskStarted(event) {
    updateTaskStatus(event.task_id, 'running', event.message);
    addProgressIndicator(event.task_id, event.task_title, event.role, event.model);
}

function handleTaskProgress(event) {
    updateProgressBar(event.task_id, event.progress, event.message);
}

function handleTaskCompleted(event) {
    updateTaskStatus(event.task_id, 'completed', `✅ 完成 (${Math.round(event.duration_ms)}ms)`);
    removeProgressIndicator(event.task_id);

    // 显示输出
    if (event.output) {
        const roleInfo = getRoleInfo(event.role);
        addMessage(
            `${roleInfo.icon} ${roleInfo.label} (${event.model})`,
            event.output,
            'agent'
        );
    }
}

function handleTaskFailed(event) {
    updateTaskStatus(event.task_id, 'failed', event.message);
    removeProgressIndicator(event.task_id);
}

function handleAllCompleted(event) {
    document.getElementById('leader-status').textContent = '✅ 全部完成';
    updateStatus('completed', event.message);
    addMessage('leader', event.message, 'leader');
}

// ============ UI 操作 ============
function createTaskElement(task) {
    const el = document.createElement('div');
    el.className = 'task-item';
    el.id = `task-${task.id}`;
    el.onclick = () => scrollToTask(task.id);

    const statusIcons = {
        pending: '⏳',
        running: '🔄',
        completed: '✓',
        failed: '✗',
    };

    el.innerHTML = `
        <div class="task-header">
            <span class="task-status-icon status-${task.status}">${statusIcons[task.status] || '⏳'}</span>
            <span class="task-title">${task.title}</span>
        </div>
        <div class="task-meta">
            <span class="task-role-dot" style="background:${task.role_color}"></span>
            <span>${task.role_icon} ${task.role_label}</span>
            <span class="task-model">${task.model}</span>
        </div>
    `;
    return el;
}

function updateTaskStatus(taskId, status, message) {
    const el = document.getElementById(`task-${taskId}`);
    if (!el) return;

    const statusIcons = {
        pending: '⏳',
        running: '🔄',
        completed: '✓',
        failed: '✗',
    };

    const icon = el.querySelector('.task-status-icon');
    if (icon) {
        icon.textContent = statusIcons[status] || '⏳';
        icon.className = `task-status-icon status-${status}`;
    }

    if (tasks[taskId]) {
        tasks[taskId].status = status;
    }
}

function addMessage(sender, content, type) {
    const conv = document.getElementById('conversation');
    document.getElementById('conv-empty')?.remove();

    const msg = document.createElement('div');
    msg.className = `msg ${type}`;

    // 简单 markdown 渲染
    const rendered = renderContent(content);

    msg.innerHTML = `
        <div class="msg-header">${sender}</div>
        <div class="msg-body">${rendered}</div>
    `;

    conv.appendChild(msg);
    conv.scrollTop = conv.scrollHeight;
}

function addProgressIndicator(taskId, title, role, model) {
    const conv = document.getElementById('conversation');
    const roleInfo = getRoleInfo(role);

    const el = document.createElement('div');
    el.className = 'progress-indicator';
    el.id = `progress-${taskId}`;
    el.innerHTML = `
        <div class="spinner"></div>
        <span>${roleInfo.icon} ${title} <span style="opacity:0.6">(${model})</span></span>
    `;

    conv.appendChild(el);
    conv.scrollTop = conv.scrollHeight;
}

function updateProgressBar(taskId, progress, message) {
    const el = document.getElementById(`progress-${taskId}`);
    if (!el) return;
    const span = el.querySelector('span');
    if (span) {
        const roleIcon = span.textContent.split(' ')[0];
        span.innerHTML = `${message} <span style="opacity:0.5">${Math.round(progress*100)}%</span>`;
    }
}

function removeProgressIndicator(taskId) {
    const el = document.getElementById(`progress-${taskId}`);
    if (el) el.remove();
}

function scrollToTask(taskId) {
    // highlight task
    document.querySelectorAll('.task-item').forEach(el => el.classList.remove('active'));
    const el = document.getElementById(`task-${taskId}`);
    if (el) el.classList.add('active');
}

function renderContent(text) {
    if (!text) return '';
    // Escape HTML
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Code blocks
    html = html.replace(/```(\\w*)\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
    html = html.replace(/```([\\s\\S]*?)```/g, '<pre><code>$1</code></pre>');
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold
    html = html.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
    // Newlines
    html = html.replace(/\\n/g, '<br>');
    return html;
}

function getRoleInfo(role) {
    const info = {
        python_dev: { icon: '🐍', label: 'Python 开发' },
        frontend_dev: { icon: '⚛️', label: '前端开发' },
        backend_dev: { icon: '🔧', label: '后端开发' },
        test_engineer: { icon: '🧪', label: '测试工程师' },
        security_auditor: { icon: '🛡️', label: '安全审计' },
        architect: { icon: '🏗️', label: '架构师' },
        devops: { icon: '🚀', label: 'DevOps' },
        database_expert: { icon: '🗄️', label: '数据库专家' },
        code_reviewer: { icon: '👁️', label: '代码审查' },
    };
    return info[role] || { icon: '🤖', label: 'Agent' };
}

function setExecuting(val) {
    isExecuting = val;
    document.getElementById('send-btn').disabled = val;
    document.getElementById('message-input').disabled = val;
}

// ============ 发送消息 ============
function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (!message || isExecuting) return;

    // 显示用户消息
    addMessage('你', message, 'user');
    input.value = '';

    setExecuting(true);

    // 通过 WebSocket 发送
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'message', content: message }));
    }
}

// Enter 键发送
document.getElementById('message-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// 启动
init();
</script>
</body>
</html>"""
