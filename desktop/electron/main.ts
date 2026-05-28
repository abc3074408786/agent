import { app, BrowserWindow, ipcMain, shell } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs'

// 禁用 GPU 缓存错误 (Windows)
app.commandLine.appendSwitch('disable-gpu-cache')

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null

const PYTHON_SERVER_PORT = 8080
const isDev = !app.isPackaged

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'Agent Desktop - 团队协作',
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#1a1b26',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // 开发模式加载 Vite dev server
  if (isDev && process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    // 生产模式加载打包后的文件
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // 外部链接用默认浏览器打开
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// ============ Python 后端进程管理 ============

function findPythonPath(): string {
  // 按优先级查找 Python
  const candidates = [
    'python3',
    'python',
    path.join(process.env.CONDA_PREFIX || '', 'python'),
    path.join(process.env.VIRTUAL_ENV || '', 'bin', 'python'),
    path.join(process.env.VIRTUAL_ENV || '', 'Scripts', 'python.exe'),
  ]

  for (const candidate of candidates) {
    try {
      const result = require('child_process').execSync(`${candidate} --version`, {
        encoding: 'utf-8',
        timeout: 5000,
      })
      if (result.includes('Python')) {
        return candidate
      }
    } catch {
      continue
    }
  }
  return 'python'
}

function getAgentRootPath(): string {
  // 查找 agent 项目根目录
  if (isDev) {
    // 开发模式: desktop/ 同级的 agent 目录
    return path.resolve(__dirname, '..', '..')
  } else {
    // 打包模式: 查找资源目录
    const resourcePath = path.join(process.resourcesPath, 'agent')
    if (fs.existsSync(resourcePath)) {
      return resourcePath
    }
    return path.resolve(app.getAppPath(), '..', '..')
  }
}

function startPythonServer(): void {
  const pythonPath = findPythonPath()
  const agentRoot = getAgentRootPath()
  const scriptPath = path.join(agentRoot, 'run_team_ui.py')

  if (!fs.existsSync(scriptPath)) {
    console.warn(`⚠️  Python script not found: ${scriptPath}`)
    console.warn('   Running in frontend-only mode (no backend)')
    sendToRenderer('python-status', { status: 'not-found', path: scriptPath })
    return
  }

  console.log(`🐍 Starting Python server: ${pythonPath} ${scriptPath}`)
  console.log(`   Working dir: ${agentRoot}`)

  pythonProcess = spawn(pythonPath, [scriptPath, '--port', String(PYTHON_SERVER_PORT)], {
    cwd: agentRoot,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  })

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    console.log(`[Python] ${msg}`)
    sendToRenderer('python-log', { message: msg })

    // 检测服务器启动成功
    if (msg.includes('running at') || msg.includes('Starting')) {
      sendToRenderer('python-status', { status: 'running', port: PYTHON_SERVER_PORT })
    }
  })

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    console.error(`[Python Error] ${msg}`)
    sendToRenderer('python-log', { message: msg, level: 'error' })
  })

  pythonProcess.on('exit', (code) => {
    console.log(`[Python] Process exited with code ${code}`)
    sendToRenderer('python-status', { status: 'stopped', code })
    pythonProcess = null
  })

  pythonProcess.on('error', (err) => {
    console.error(`[Python] Failed to start: ${err.message}`)
    sendToRenderer('python-status', { status: 'error', error: err.message })
    pythonProcess = null
  })
}

function stopPythonServer(): void {
  if (pythonProcess) {
    console.log('🛑 Stopping Python server...')
    pythonProcess.kill('SIGTERM')
    setTimeout(() => {
      if (pythonProcess && !pythonProcess.killed) {
        pythonProcess.kill('SIGKILL')
      }
    }, 3000)
  }
}

function sendToRenderer(channel: string, data: any): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, data)
  }
}

// ============ IPC Handlers ============

ipcMain.handle('get-server-info', () => {
  return {
    port: PYTHON_SERVER_PORT,
    isRunning: pythonProcess !== null && !pythonProcess.killed,
    agentRoot: getAgentRootPath(),
  }
})

ipcMain.handle('start-python-server', () => {
  if (!pythonProcess || pythonProcess.killed) {
    startPythonServer()
    return { status: 'starting' }
  }
  return { status: 'already-running' }
})

ipcMain.handle('stop-python-server', () => {
  stopPythonServer()
  return { status: 'stopping' }
})

ipcMain.handle('get-app-info', () => {
  return {
    version: app.getVersion(),
    platform: process.platform,
    isDev,
    electronVersion: process.versions.electron,
    nodeVersion: process.versions.node,
  }
})

// ============ App Lifecycle ============

app.whenReady().then(() => {
  createWindow()
  startPythonServer()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  stopPythonServer()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopPythonServer()
})
