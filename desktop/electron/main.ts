import { app, BrowserWindow, ipcMain, shell } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs'

let mainWindow: BrowserWindow | null = null
let agentProcess: ChildProcess | null = null

// Python Agent 进程管理
function findPythonPath(): string {
  // 优先使用捆绑的 Python
  const bundledPython = path.join(process.resourcesPath, 'python', 'python')
  if (fs.existsSync(bundledPython)) {
    return bundledPython
  }
  // Windows 捆绑路径
  const bundledPythonWin = path.join(process.resourcesPath, 'python', 'python.exe')
  if (fs.existsSync(bundledPythonWin)) {
    return bundledPythonWin
  }
  // 降级到系统 Python
  return process.platform === 'win32' ? 'python' : 'python3'
}

function getAgentPath(): string {
  // 开发模式下的路径
  if (!app.isPackaged) {
    return path.join(__dirname, '..', '..', 'agent')
  }
  // 打包后的路径
  return path.join(process.resourcesPath, 'agent')
}

function startAgentProcess(port: number = 8765): void {
  const pythonPath = findPythonPath()
  const agentPath = getAgentPath()

  console.log(`Starting Agent: ${pythonPath} at ${agentPath}`)

  agentProcess = spawn(pythonPath, [
    '-m', 'uvicorn',
    'agent.api:create_app',
    '--factory',
    '--host', '127.0.0.1',
    '--port', port.toString()
  ], {
    cwd: agentPath,
    env: {
      ...process.env,
      AGENT_PORT: port.toString()
    },
    stdio: ['pipe', 'pipe', 'pipe']
  })

  agentProcess.stdout?.on('data', (data) => {
    console.log(`[Agent] ${data.toString()}`)
    mainWindow?.webContents.send('agent:log', data.toString())
  })

  agentProcess.stderr?.on('data', (data) => {
    console.error(`[Agent Error] ${data.toString()}`)
    mainWindow?.webContents.send('agent:error', data.toString())
  })

  agentProcess.on('close', (code) => {
    console.log(`Agent process exited with code ${code}`)
    mainWindow?.webContents.send('agent:status', 'stopped')
    agentProcess = null
  })

  agentProcess.on('error', (err) => {
    console.error('Failed to start Agent:', err)
    mainWindow?.webContents.send('agent:status', 'error')
  })
}

function stopAgentProcess(): void {
  if (agentProcess) {
    agentProcess.kill('SIGTERM')
    agentProcess = null
  }
}

// 窗口创建
function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 12, y: 12 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  // 开发模式加载 Vite dev server
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // 外部链接用系统浏览器打开
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// IPC 处理
ipcMain.handle('agent:start', async (_event, port: number = 8765) => {
  startAgentProcess(port)
  return { success: true, port }
})

ipcMain.handle('agent:stop', async () => {
  stopAgentProcess()
  return { success: true }
})

ipcMain.handle('agent:status', async () => {
  return { running: agentProcess !== null }
})

ipcMain.handle('window:minimize', () => {
  mainWindow?.minimize()
})

ipcMain.handle('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})

ipcMain.handle('window:close', () => {
  mainWindow?.close()
})

ipcMain.handle('window:isMaximized', () => {
  return mainWindow?.isMaximized() ?? false
})

// 获取用户数据路径（存储配置等）
ipcMain.handle('app:getDataPath', () => {
  return app.getPath('userData')
})

// 应用生命周期
app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  stopAgentProcess()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopAgentProcess()
})
