import type { ThinkingMode } from '@/shared/api/types'

const DEFAULT_MODEL_OPTIONS = [
  'deepseek-ai/DeepSeek-V4-Flash',
  'gpt-4.1-mini',
] as const

export type ChatModel = string

export function resolveModelOptions(value: unknown): readonly string[] {
  if (typeof value !== 'string') return DEFAULT_MODEL_OPTIONS

  const configured = [...new Set(value.split(',').map(model => model.trim()).filter(Boolean))]
  return configured.length > 0 ? configured : DEFAULT_MODEL_OPTIONS
}

export const MODEL_OPTIONS = resolveModelOptions(import.meta.env.VITE_CHAT_MODELS)

export const DEFAULT_CHAT_MODEL: ChatModel = MODEL_OPTIONS[0]

export const THINKING_OPTIONS: Array<{
  value: ThinkingMode
  label: string
  detail: string
}> = [
  { value: 'fast', label: 'Rápido', detail: 'direto' },
  { value: 'balanced', label: 'Equilibrado', detail: 'exemplos' },
  { value: 'deep', label: 'Profundo', detail: 'trade-offs' },
]

export const SUGGESTIONS = [
  'Como criar uma lista em Python?',
  'Explique fixtures do pytest com exemplo',
  'Como estruturar uma API Flask com SQLAlchemy?',
  'Revise este erro de tipagem em Python',
]

export function resolveThinkingMode(value: unknown): ThinkingMode {
  return THINKING_OPTIONS.some(option => option.value === value)
    ? (value as ThinkingMode)
    : 'balanced'
}

export function thinkingModeLabel(value: ThinkingMode): string {
  return THINKING_OPTIONS.find(option => option.value === value)?.label ?? 'Equilibrado'
}
