import { useEffect } from 'react'
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useAppStore, ToastType } from '../store'

const icons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 size={18} className="text-accent-green" />,
  error: <XCircle size={18} className="text-accent-red" />,
  warning: <AlertTriangle size={18} className="text-accent-amber" />,
  info: <Info size={18} className="text-accent-blue" />,
}

const bgClasses: Record<ToastType, string> = {
  success: 'bg-[var(--toast-success-bg)] border-[var(--toast-success-border)]',
  error: 'bg-[var(--toast-error-bg)] border-[var(--toast-error-border)]',
  warning: 'bg-[var(--toast-warning-bg)] border-[var(--toast-warning-border)]',
  info: 'bg-[var(--toast-info-bg)] border-[var(--toast-info-border)]',
}

export default function ToastContainer() {
  const { toasts, removeToast } = useAppStore()

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`animate-slide-in-up flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg ${bgClasses[toast.type]}`}
        >
          <span className="mt-0.5 shrink-0">{icons[toast.type]}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text-primary">{toast.title}</p>
            {toast.description && (
              <p className="text-xs text-text-secondary mt-0.5">{toast.description}</p>
            )}
          </div>
          <button
            onClick={() => removeToast(toast.id)}
            className="shrink-0 p-0.5 text-text-tertiary hover:text-text-primary transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
