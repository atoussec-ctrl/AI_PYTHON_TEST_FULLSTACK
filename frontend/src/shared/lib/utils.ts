import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  if (Number.isNaN(date.getTime())) return 'Data inválida'

  const diffMs = date.getTime() - now.getTime()
  const absoluteMs = Math.abs(diffMs)
  const formatter = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' })

  if (absoluteMs < 60_000) return formatter.format(0, 'second')
  if (absoluteMs < 3_600_000) {
    return formatter.format(Math.round(diffMs / 60_000), 'minute')
  }
  if (absoluteMs < 86_400_000) {
    return formatter.format(Math.round(diffMs / 3_600_000), 'hour')
  }
  if (absoluteMs < 604_800_000) {
    return formatter.format(Math.round(diffMs / 86_400_000), 'day')
  }
  return date.toLocaleDateString('pt-BR')
}

export function groupSessionsByDate<T extends { updated_at: string }>(
  sessions: T[]
): { label: string; items: T[] }[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)
  const monthAgo = new Date(today.getTime() - 30 * 86400000)

  const groups: { label: string; items: T[] }[] = [
    { label: 'Hoje', items: [] },
    { label: 'Ontem', items: [] },
    { label: 'Últimos 7 dias', items: [] },
    { label: 'Últimos 30 dias', items: [] },
    { label: 'Mais antigas', items: [] },
  ]

  for (const session of sessions) {
    const date = new Date(session.updated_at)
    if (date >= today) {
      groups[0].items.push(session)
    } else if (date >= yesterday) {
      groups[1].items.push(session)
    } else if (date >= weekAgo) {
      groups[2].items.push(session)
    } else if (date >= monthAgo) {
      groups[3].items.push(session)
    } else {
      groups[4].items.push(session)
    }
  }

  return groups.filter(g => g.items.length > 0)
}

export function groupSessionsForSidebar<
  T extends { updated_at: string; pinned: boolean; pinned_at?: string | null },
>(sessions: T[]): { pinned: T[]; groups: { label: string; items: T[] }[] } {
  const pinned = sessions
    .filter(session => session.pinned)
    .sort(
      (left, right) =>
        new Date(right.pinned_at ?? right.updated_at).getTime() -
        new Date(left.pinned_at ?? left.updated_at).getTime(),
    )

  const groups = groupSessionsByDate(sessions.filter(session => !session.pinned))

  return { pinned, groups }
}

export function filterSessionsByQuery<T extends { title: string }>(
  sessions: T[],
  query: string,
): T[] {
  const normalized = query.trim().toLowerCase()
  if (!normalized) return sessions
  return sessions.filter(session => session.title.toLowerCase().includes(normalized))
}
