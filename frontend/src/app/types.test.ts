import { describe, expect, it } from 'vitest'

import { resolveTheme } from './types'

describe('resolveTheme', () => {
  it('accepts dark and defaults every other value to light', () => {
    expect(resolveTheme('dark')).toBe('dark')
    expect(resolveTheme('light')).toBe('light')
    expect(resolveTheme('sepia')).toBe('light')
    expect(resolveTheme(null)).toBe('light')
  })
})
