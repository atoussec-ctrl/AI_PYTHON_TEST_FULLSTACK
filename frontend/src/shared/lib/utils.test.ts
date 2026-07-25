import { describe, expect, it, vi } from 'vitest'

import {
  filterSessionsByQuery,
  formatFileSize,
  formatRelativeTime,
  groupSessionsByDate,
  groupSessionsForSidebar,
} from './utils'

describe('utils', () => {
  it('formats file sizes', () => {
    expect(formatFileSize(0)).toBe('0 B')
    expect(formatFileSize(1536)).toBe('1.5 KB')
  })

  it('formats relative time buckets', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-12T12:00:00Z'))

    expect(formatRelativeTime('2026-06-12T11:59:30Z')).toBe('agora')
    expect(formatRelativeTime('2026-06-12T11:30:00Z')).toBe('há 30 minutos')
    expect(formatRelativeTime('2026-06-12T11:00:00Z')).toBe('há 1 hora')
    expect(formatRelativeTime('2026-06-10T12:00:00Z')).toBe('anteontem')

    vi.useRealTimers()
  })

  it('falls back to a localized date for anything a week or older', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-12T12:00:00Z'))

    const oldDate = new Date('2026-04-01T12:00:00Z')

    expect(formatRelativeTime(oldDate.toISOString())).toBe(
      oldDate.toLocaleDateString('pt-BR'),
    )

    vi.useRealTimers()
  })

  it('groups sessions by recency', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-12T12:00:00Z'))

    const groups = groupSessionsByDate([
      { updated_at: '2026-06-12T10:00:00Z' },
      { updated_at: '2026-06-11T10:00:00Z' },
      { updated_at: '2026-06-08T10:00:00Z' },
      { updated_at: '2026-05-01T10:00:00Z' },
    ])

    expect(groups.map(group => group.label)).toEqual([
      'Hoje',
      'Ontem',
      'Últimos 7 dias',
      'Mais antigas',
    ])

    vi.useRealTimers()
  })

  it('assigns sessions to the previous 30 days bucket', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-12T12:00:00Z'))

    // 15 days ago: older than 7 days but within 30 days
    const groups = groupSessionsByDate([{ updated_at: '2026-05-28T12:00:00Z' }])

    expect(groups).toHaveLength(1)
    expect(groups[0].label).toBe('Últimos 30 dias')

    vi.useRealTimers()
  })

  it('separates pinned sessions from recent groups', () => {
    const layout = groupSessionsForSidebar([
      {
        updated_at: '2026-06-12T10:00:00Z',
        pinned: true,
        pinned_at: '2026-06-12T09:00:00Z',
      },
      {
        updated_at: '2026-06-11T10:00:00Z',
        pinned: false,
        pinned_at: null,
      },
    ])

    expect(layout.pinned).toHaveLength(1)
    expect(layout.groups).toHaveLength(1)
    expect(layout.groups[0].items).toHaveLength(1)
  })

  it('sorts pinned sessions by pinned_at, falling back to updated_at when null', () => {
    const layout = groupSessionsForSidebar([
      {
        updated_at: '2026-06-10T10:00:00Z',
        pinned: true,
        pinned_at: null, // falls back to updated_at for sort
      },
      {
        updated_at: '2026-06-12T10:00:00Z',
        pinned: true,
        pinned_at: '2026-06-12T08:00:00Z',
      },
    ])

    expect(layout.pinned).toHaveLength(2)
    // Most recently pinned should come first (2026-06-12 > 2026-06-10)
    expect(layout.pinned[0].updated_at).toBe('2026-06-12T10:00:00Z')
  })

  it('filters sessions by a case-insensitive title match', () => {
    const sessions = [
      { id: '1', title: 'Dúvida sobre Flask' },
      { id: '2', title: 'Listas em Python' },
      { id: '3', title: 'SQLAlchemy e migrations' },
    ]

    expect(filterSessionsByQuery(sessions, 'flask')).toEqual([sessions[0]])
    expect(filterSessionsByQuery(sessions, 'PYTHON')).toEqual([sessions[1]])
  })

  it('returns every session when the query is empty or blank', () => {
    const sessions = [{ id: '1', title: 'Dúvida sobre Flask' }]

    expect(filterSessionsByQuery(sessions, '')).toEqual(sessions)
    expect(filterSessionsByQuery(sessions, '   ')).toEqual(sessions)
  })

  it('returns an empty list when nothing matches', () => {
    const sessions = [{ id: '1', title: 'Dúvida sobre Flask' }]

    expect(filterSessionsByQuery(sessions, 'inexistente')).toEqual([])
  })
})
