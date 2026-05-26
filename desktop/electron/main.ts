import { app, BrowserWindow, ipcMain, shell, safeStorage } from 'electron'
import { spawn, ChildProcess, execSync } from 'child_process'
import path from 'path'
import fs from 'fs'
import http from 'http'

let mainWindow: BrowserWindow | null = null
let agentProcess: ChildProcess | null = null

// ============================================================
// API Key 加密存储（使用 Electron safeStorage）
// ============================================================

const secretsFilePath = () => path.join(app.getPath('userData'), 'secrets.enc.json')

function saveEncryptedSecrets(secrets: Record<string, string>): void {
  if (!safeStorage.isEncryptionAvailable()) {
    // 降级：明文存储（开发模式或不支持加密的系统）
    fs.writeFileSync(secretsFilePath(), JSON.stringify(secrets), 'utf-8')
    return
  }

  const encrypted: Record<string, string> = {}
  for (const [key, value] of Object.entries(secrets)) {
    if (value) {
      const buffer = safeStorage.encryptString(value)
      encrypted[key] = buffer.toString('base64')
    }
  }
  fs.writeFileSync(secretsFilePath(), JSON.stringify(encrypted), 'utf-8')
}

function loadEncryptedSecrets(): Record<string, string> {
  const filePath = secretsFilePath()
  if (!fs.existsSync(filePath)) return {}

  try {
    const raw = JSON.parse(fs.readFileSync(filePath, 'utf-8'))

    if (!safeStorage.isEncryptionAvailable()) {
      return raw
    }

    const decrypted: Record<string, string> = {}
    for (const [key, value] of Object.entries(raw)) {
      try {
        const buffer = Buffer.from(value as string, 'base64')
        decrypted[key] = safeStorage.decryptString(buffer)
      } catch {
        decrypted[key] = value as string // 降级：可能是未加密的旧数据
      }
    }
    return decrypted
  } catch {
    return {}
  }
}

// ============================================================
// Python Agent 进程管理
// ============================================================

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
  if (agentProcess) {
    console.log('Agent process already running')
    return
  }

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
    const log = data.toString()
    console.log(`[Agent] ${log}`)
    mainWindow?.webContents.send('agent:log', log)
  })

  agentProcess.stderr?.on('data', (data) => {
    const log = data.toString()
    // uvicorn 正常日志也走 stderr
    console.log(`[Agent] ${log}`)
    mainWindow?.webContents.send('agent:log', log)
  })

  agentProcess.on('close', (code) => {
    console.log(`Agent process exited with code ${code}`)
    mainWindow?.webContents.send('agent:status-change', 'stopped')
    agentProcess = null
  })

  agentProcess.on('error', (err) => {
    console.error('Failed to start Agent:', err)
    mainWindow?.webContents.send('agent:status-change', 'error')
    agentProcess = null
  })
}

// P1 修复：跨平台停止进程
function stopAgentProcess(): void {
  if (!agentProcess) return

  if (process.platform === 'win32') {
    // Windows: 使用 taskkill 终止进程树
    try {
      if (agentProcess.pid) {
        execSync(`taskkill /pid ${agentProcess.pid} /T /F`, { stdio: 'ignore' })
      }
    } catch {
      // 进程可能已经退出
      agentProcess.kill()
    }
  } else {
    // macOS/Linux: 发送 SIGTERM，等 3 秒后 SIGKILL
    agentProcess.kill('SIGTERM')
    const pid = agentProcess.pid
    setTimeout(() => {
      try {
        if (pid) process.kill(pid, 0) // 检查进程是否存在
        if (pid) process.kill(pid, 'SIGKILL')
      } catch {
        // 已退出
      }
    }, 3000)
  }

  agentProcess = null
}

// P1 修复：轮询 /health 等待 Agent 启动完成
function waitForAgentReady(port: number, timeoutMs: number = 30000): Promise<boolean> {
  return new Promise((resolve) => {
    const startTime = Date.now()
    const interval = setInterval(() => {
      if (Date.now() - startTime > timeoutMs) {
        clearInterval(interval)
        resolve(false)
        return
      }

      const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
        if (res.statusCode === 200) {
          clearInterval(interval)
          resolve(true)
        }
      })

      req.on('error', () => {
        // Agent 还没准备好，继续等待
      })

      req.setTimeout(1000, () => {
        req.destroy()
      })
    }, 500)
  })
}

// ============================================================
// 窗口创建
// ============================================================

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

// ============================================================
// IPC 处理
// ============================================================

// Agent 管理
ipcMain.handle('agent:start', async (_event, port: number = 8765) => {
  startAgentProcess(port)
  mainWindow?.webContents.send('agent:status-change', 'starting')

  // 等待 Agent 启动完成
  const ready = await waitForAgentReady(port)
  if (ready) {
    mainWindow?.webContents.send('agent:status-change', 'running')
    return { success: true, port }
  } else {
    mainWindow?.webContents.send('agent:status-change', 'error')
    return { success: false, port, error: 'Agent 启动超时（30秒）' }
  }
})

ipcMain.handle('agent:stop', async () => {
  stopAgentProcess()
  return { success: true }
})

ipcMain.handle('agent:status', async () => {
  return { running: agentProcess !== null }
})

// 加密存储管理
ipcMain.handle('secrets:save', async (_event, secrets: Record<string, string>) => {
  try {
    saveEncryptedSecrets(secrets)
    return { success: true }
  } catch (error) {
    return { success: false, error: (error as Error).message }
  }
})

ipcMain.handle('secrets:load', async () => {
  try {
    return { success: true, secrets: loadEncryptedSecrets() }
  } catch (error) {
    return { success: false, error: (error as Error).message, secrets: {} }
  }
})

// 窗口控制
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

// 获取用户数据路径
ipcMain.handle('app:getDataPath', () => {
  return app.getPath('userData')
})

// ============================================================
// 应用生命周期
// ============================================================

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
