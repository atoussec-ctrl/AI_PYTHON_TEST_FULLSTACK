import { afterEach, describe, expect, it, vi } from 'vitest'

import { readApiCredential, saveApiCredential } from './credentials'

describe('runtime API credentials', () => {
  afterEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('stores a normalized credential for the current browser session', () => {
    saveApiCredential('  secret  ')

    expect(readApiCredential()).toBe('secret')
  })

  it('removes blank credentials', () => {
    saveApiCredential('secret')
    saveApiCredential('   ')

    expect(readApiCredential()).toBe('')
  })

  it('degrades safely when browser storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage disabled')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage disabled')
    })

    expect(() => saveApiCredential('secret')).not.toThrow()
    expect(readApiCredential()).toBe('')
  })
})
