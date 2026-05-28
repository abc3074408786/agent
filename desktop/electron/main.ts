import { app, BrowserWindow, ipcMain, shell } from 'electron'
import { spawn, ChildProcess, execSync } from 'child_process'
import path from 'path'
import fs from 'fs'

// 禁用 Windows GPU 缓存错误
app.commandLine.appendSwitch('disable-gpu-cache')
app.commandLine.appendSwitch('disable-gpu')

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null

const PYTHON_SERVER_PORT = 8080
const isDev = !app.isPackaged

// vite-plugin-electron 会注入这个环境变量
const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'Agent Desktop - 团队协作',
    backgroundColor: '#1a1b26',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // 窗口准备好再显示，避免白屏闪烁
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  if (VITE_DEV_SERVER_URL) {
    // 开发模式: vite-plugin-electron 自动注入 URL
    console.log(`[Electron] Loading dev server: ${VITE_DEV_SERVER_URL}`)
    mainWindow.loadURL(VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    // 生产模式: 加载打包后的 HTML
    const htmlPath = path.join(__dirname, '../dist/index.html')
    console.log(`[Electron] Loading file: ${htmlPath}`)
    mainWindow.loadFile(htmlPath)
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// ============ Python 后端管理 ============

function findPythonPath(): string {
  // Windows 优先 python, Linux/Mac 优先 python3
  const isWin = process.platform === 'win32'
  const candidates = isWin
    ? ['python', 'python3', 'py']
    : ['python3', 'python']

  for (const cmd of candidates) {
    try {
      const result = execSync(`${cmd} --version`, {
        encoding: 'utf-8',
        timeout: 5000,
        stdio: ['pipe', 'pipe', 'pipe'],
      })
      if (result.includes('Python 3')) {
        console.log(`[Python] Found: ${cmd} -> ${result.trim()}`)
        return cmd
      }
    } catch {
      continue
    }
  }

  console.warn('[Python] No Python 3 found in PATH')
  return isWin ? 'python' : 'python3'
}

function getAgentRootPath(): string {
  if (isDev) {
    // 开发模式: desktop 的父目录就是项目根
    // __dirname 在 dev 模式下是 dist-electron/
    // 所以 ../.. 到项目根
    const devRoot = path.resolve(__dirname, '..')
    const parentRoot = path.resolve(devRoot, '..')

    // 检查 run_team_ui.py 在哪个层级
    if (fs.existsSync(path.join(devRoot, 'run_team_ui.py'))) {
      return devRoot
    }
    if (fs.existsSync(path.join(parentRoot, 'run_team_ui.py'))) {
      return parentRoot
    }
    // 默认返回父目录
    return parentRoot
  } else {
    // 打包模式
    const resourcePath = path.join(process.resourcesPath)
    if (fs.existsSync(path.join(resourcePath, 'run_team_ui.py'))) {
      return resourcePath
    }
    return path.resolve(app.getAppPath(), '..')
  }
}

function startPythonServer(): void {
  const pythonPath = findPythonPath()
  const agentRoot = getAgentRootPath()
  const scriptPath = path.join(agentRoot, 'run_team_ui.py')

  console.log(`[Python] Agent root: ${agentRoot}`)
  console.log(`[Python] Script path: ${scriptPath}`)

  if (!fs.existsSync(scriptPath)) {
    console.warn(`[Python] ⚠️ Script not found: ${scriptPath}`)
    console.warn('[Python] Running in frontend-only mode')
    sendToRenderer('python-status', { status: 'not-found', path: scriptPath })
    return
  }

  console.log(`[Python] Starting: ${pythonPath} ${scriptPath} --port ${PYTHON_SERVER_PORT}`)

  pythonProcess = spawn(pythonPath, [scriptPath, '--port', String(PYTHON_SERVER_PORT)], {
    cwd: agentRoot,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    if (msg) {
      console.log(`[Python] ${msg}`)
      sendToRenderer('python-log', { message: msg })
      if (msg.includes('running at') || msg.includes('Starting') || msg.includes('Server')) {
        sendToRenderer('python-status', { status: 'running', port: PYTHON_SERVER_PORT })
      }
    }
  })

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    if (msg) {
      console.error(`[Python ERR] ${msg}`)
      sendToRenderer('python-log', { message: msg, level: 'error' })
    }
  })

  pythonProcess.on('exit', (code) => {
    console.log(`[Python] Exited with code ${code}`)
    sendToRenderer('python-status', { status: 'stopped', code })
    pythonProcess = null
  })

  pythonProcess.on('error', (err) => {
    console.error(`[Python] Spawn error: ${err.message}`)
    sendToRenderer('python-status', { status: 'error', error: err.message })
    pythonProcess = null
  })
}

function stopPythonServer(): void {
  if (pythonProcess && !pythonProcess.killed) {
    console.log('[Python] Stopping server...')
    if (process.platform === 'win32') {
      // Windows: 用 taskkill 强制结束进程树
      try {
        execSync(`taskkill /pid ${pythonProcess.pid} /T /F`, { stdio: 'pipe' })
      } catch {
        pythonProcess.kill()
      }
    } else {
      pythonProcess.kill('SIGTERM')
      setTimeout(() => {
        if (pythonProcess && !pythonProcess.killed) {
          pythonProcess.kill('SIGKILL')
        }
      }, 3000)
    }
  }
}

function sendToRenderer(channel: string, data: any): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, data)
  }
}

// ============ IPC ============

ipcMain.handle('get-server-info', () => ({
  port: PYTHON_SERVER_PORT,
  isRunning: pythonProcess !== null && !pythonProcess.killed,
  agentRoot: getAgentRootPath(),
}))

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

ipcMain.handle('get-app-info', () => ({
  version: app.getVersion(),
  platform: process.platform,
  isDev,
  electronVersion: process.versions.electron,
  nodeVersion: process.versions.node,
}))

// ============ App Lifecycle ============

app.whenReady().then(() => {
  createWindow()

  // 延迟一点启动 Python，让窗口先显示
  setTimeout(() => startPythonServer(), 1000)

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
