export type AppView = 'chat' | 'books' | 'settings'

export type AppTheme = 'light' | 'dark'

export function resolveTheme(value: string | null): AppTheme {
  return value === 'dark' ? 'dark' : 'light'
}
