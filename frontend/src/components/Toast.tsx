import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { messageForError } from '../api/errorMessages'

interface ToastContextValue {
  showError: (error: unknown) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null)
  const showError = useCallback((error: unknown) => setMessage(messageForError(error)), [])
  const value = useMemo(() => ({ showError }), [showError])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {message && (
        <div role="alert" className="toast">
          <span>{message}</span>
          <button type="button" onClick={() => setMessage(null)}>
            Dismiss
          </button>
        </div>
      )}
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}
