import { useEffect } from 'react'
import { Wifi, WifiOff, Loader2 } from 'lucide-react'
import { useAppStore } from '../store'

export default function ConnectionStatus() {
  const { connectionStatus, setConnectionStatus, settings, addToast } = useAppStore()

  // Poll health check
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>

    const check = async () => {
      setConnectionStatus('checking')
      const baseUrl = settings.agentMode === 'local'
        ? `http://127.0.0.1:${settings.agentLocalPort}`
        : settings.agentRemoteUrl

      if (!baseUrl) {
        setConnectionStatus('disconnected')
        return
      }

      try {
        const resp = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(3000) })
        if (resp.ok) {
          setConnectionStatus('connected')
        } else {
          setConnectionStatus('disconnected')
        }
      } catch {
        setConnectionStatus('disconnected')
      }
    }

    check()
    timer = setInterval(check, 30000)
    return () => clearInterval(timer)
  }, [settings.agentMode, settings.agentLocalPort, settings.agentRemoteUrl])

  const statusConfig = {
    connected: { icon: <Wifi size={12} />, color: 'text-accent-green', bg: 'bg-green-500/10', label: '已连接' },
    disconnected: { icon: <WifiOff size={12} />, color: 'text-accent-red', bg: 'bg-red-500/10', label: '未连接' },
    checking: { icon: <Loader2 size={12} className="animate-spin" />, color: 'text-accent-amber', bg: 'bg-amber-500/10', label: '检测中' },
  }

  const cfg = statusConfig[connectionStatus]

  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium ${cfg.color} ${cfg.bg} transition-all`}
      title={`Agent 服务: ${cfg.label}`}
    >
      {cfg.icon}
      <span className="hidden sm:inline">{cfg.label}</span>
    </div>
  )
}
