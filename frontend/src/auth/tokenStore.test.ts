import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createTokenStore } from './tokenStore'

describe('token store', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  it('keeps the token in memory and in sessionStorage, never localStorage', () => {
    const store = createTokenStore()

    store.set('tok-1')

    expect(store.get()).toBe('tok-1')
    expect(sessionStorage.getItem('cc.token')).toBe('tok-1')
    expect(localStorage.length).toBe(0)
  })

  it('restores a token saved earlier in the same browser session', () => {
    sessionStorage.setItem('cc.token', 'saved')

    expect(createTokenStore().get()).toBe('saved')
  })

  it('clear removes it everywhere', () => {
    const store = createTokenStore()
    store.set('tok-1')

    store.clear()

    expect(store.get()).toBeNull()
    expect(sessionStorage.getItem('cc.token')).toBeNull()
  })

  it('notifies subscribers on set and clear, and stops after unsubscribe', () => {
    const store = createTokenStore()
    const listener = vi.fn()
    const unsubscribe = store.subscribe(listener)

    store.set('a')
    store.clear()
    unsubscribe()
    store.set('b')

    expect(listener).toHaveBeenCalledTimes(2)
  })

  it('still works when sessionStorage is unavailable', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
      removeItem: () => {
        throw new Error('blocked')
      },
    } as unknown as Storage
    const store = createTokenStore(broken)

    store.set('mem-only')

    expect(store.get()).toBe('mem-only')
  })
})
