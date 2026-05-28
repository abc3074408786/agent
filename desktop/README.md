# Agent Desktop - 团队协作桌面应用

Electron + Vue 3 + Vite 桌面应用，实时可视化 AI Agent 团队协作。

## 快速开始

```bash
cd desktop
npm install
npm run electron:dev
```

## 架构

```
desktop/
├── electron/
│   ├── main.ts          # 主进程 (窗口管理 + Python 后端启动)
│   └── preload.ts       # IPC 桥接
├── src/
│   ├── App.vue          # 根组件 (标题栏 + 布局)
│   ├── main.ts          # Vue 入口
│   ├── stores/
│   │   └── team.ts      # Pinia 状态管理 (WebSocket + 任务状态)
│   └── components/
│       ├── TaskPanel.vue         # 左侧任务面板
│       └── ConversationPanel.vue # 右侧对话区
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 工作原理

1. Electron 主进程启动时自动 spawn Python 后端 (`run_team_ui.py`)
2. Vue 前端通过 WebSocket 连接到 Python 后端 (localhost:8080)
3. 用户输入 → WebSocket → Leader Agent 分解 → 子任务执行 → 实时推送结果

## 打包

```bash
npm run electron:build
```
