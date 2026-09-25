const KEY = 'cc.token'

type Listener = () => void

export interface TokenStore {
  get: () => string | null
  set: (token: string) => void
  clear: () => void
  subscribe: (listener: Listener) => () => void
}

/**
 * Holds the session token in memory and in sessionStorage (cleared when the tab closes).
 * Never localStorage: the token must not outlive the browser session.
 */
export function createTokenStore(storage: Storage = sessionStorage): TokenStore {
  const listeners = new Set<Listener>()

  function read(): string | null {
    try {
      return storage.getItem(KEY)
    } catch {
      return null
    }
  }

  let memory: string | null = read()

  function notify() {
    listeners.forEach((listener) => listener())
  }

  return {
    get: () => memory,
    set: (token) => {
      memory = token
      try {
        storage.setItem(KEY, token)
      } catch {
        // storage unavailable: keep the in-memory token only
      }
      notify()
    },
    clear: () => {
      memory = null
      try {
        storage.removeItem(KEY)
      } catch {
        // ignore
      }
      notify()
    },
    subscribe: (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

export const tokenStore = createTokenStore()
