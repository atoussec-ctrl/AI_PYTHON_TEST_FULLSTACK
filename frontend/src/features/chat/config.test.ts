import { describe, expect, it } from 'vitest'

import {
  DEFAULT_CHAT_MODEL,
  resolveModelOptions,
  resolveThinkingMode,
  thinkingModeLabel,
} from './config'

describe('chat configuration', () => {
  it('falls back to balanced for missing or unsupported thinking modes', () => {
    expect(resolveThinkingMode(undefined)).toBe('balanced')
    expect(resolveThinkingMode('unsupported')).toBe('balanced')
  })

  it('preserves supported modes and exposes their localized labels', () => {
    expect(resolveThinkingMode('deep')).toBe('deep')
    expect(thinkingModeLabel('fast')).toBe('Rápido')
    expect(DEFAULT_CHAT_MODEL).toBe('deepseek-ai/DeepSeek-V4-Flash')
  })

  it('normalizes configured models and falls back to backend defaults', () => {
    expect(resolveModelOptions(' custom-a, custom-b,custom-a ')).toEqual([
      'custom-a',
      'custom-b',
    ])
    expect(resolveModelOptions(' , ')).toEqual([
      'deepseek-ai/DeepSeek-V4-Flash',
      'gpt-4.1-mini',
    ])
  })
})
