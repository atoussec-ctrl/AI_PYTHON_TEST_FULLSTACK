import { useState, type ReactNode } from 'react'
import {
  BookOpen,
  Bot,
  PanelLeftClose,
  Plus,
  Search,
  Settings2,
  Sparkles,
} from 'lucide-react'

import type { AppView } from '@/app/types'
import { Button } from '@/components/ui/button'
import type { ChatSession } from '@/shared/api/types'
import { cn } from '@/shared/lib/utils'
import { ChatSessionRow } from './ChatSessionRow'
import { useSessionSwipeGesture } from './useSessionSwipeGesture'

interface ChatSidebarProps {
  pinnedSessions: ChatSession[]
  groupedSessions: Array<{ label: string; items: ChatSession[] }>
  selectedSessionId: string | null
  activeView: AppView
  isLoading: boolean
  searchQuery: string
  onSearchQueryChange: (query: string) => void
  onNewChat: () => void
  onOpenBooks: () => void
  onOpenAssistant: () => void
  onOpenSettings: () => void
  onSelectSession: (sessionId: string) => void
  onCloseSidebar: () => void
  onDeleteSession: (sessionId: string) => Promise<void>
  onPinSession: (sessionId: string, pinned: boolean) => Promise<ChatSession>
  isDeletingSession: boolean
  isPinningSession: boolean
}

export function ChatSidebar({
  pinnedSessions,
  groupedSessions,
  selectedSessionId,
  activeView,
  isLoading,
  searchQuery,
  onSearchQueryChange,
  onNewChat,
  onOpenBooks,
  onOpenAssistant,
  onOpenSettings,
  onSelectSession,
  onCloseSidebar,
  onDeleteSession,
  onPinSession,
  isDeletingSession,
  isPinningSession,
}: ChatSidebarProps) {
  const { armedSessionId, disarmSwipe, getRowHandlers } = useSessionSwipeGesture()
  const [isSearchVisible, setIsSearchVisible] = useState(false)

  async function handleDelete(sessionId: string) {
    await onDeleteSession(sessionId)
    disarmSwipe()
  }

  async function handlePin(session: ChatSession) {
    await onPinSession(session.id, !session.pinned)
    disarmSwipe()
  }

  function renderSessionRow(session: ChatSession) {
    return (
      <ChatSessionRow
        key={session.id}
        session={session}
        isSelected={activeView === 'chat' && selectedSessionId === session.id}
        isArmed={armedSessionId === session.id}
        isDeleting={isDeletingSession}
        isPinning={isPinningSession}
        rowHandlers={getRowHandlers(session.id)}
        onSelect={() => {
          disarmSwipe()
          onSelectSession(session.id)
        }}
        onDelete={() => handleDelete(session.id)}
        onPin={() => handlePin(session)}
        onDisarm={disarmSwipe}
      />
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between px-5">
        <div className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <span className="grid h-8 w-8 place-items-center rounded-md bg-primary text-primary-foreground">
            <Bot size={18} />
          </span>
          MindSight
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label="Fechar menu"
          onClick={onCloseSidebar}
        >
          <PanelLeftClose size={18} />
        </Button>
      </div>

      <div className="space-y-1 px-3">
        <SidebarButton
          icon={<Plus size={18} />}
          label="Novo chat"
          onClick={() => {
            disarmSwipe()
            onNewChat()
          }}
        />
        <SidebarButton
          icon={<Search size={18} />}
          label="Buscar chats"
          active={isSearchVisible}
          onClick={() => {
            setIsSearchVisible(current => {
              const next = !current
              if (!next) onSearchQueryChange('')
              return next
            })
          }}
        />
        {isSearchVisible ? (
          <input
            type="text"
            value={searchQuery}
            onChange={event => onSearchQueryChange(event.target.value)}
            placeholder="Buscar por título..."
            aria-label="Buscar chats"
            autoFocus
            className="h-9 w-full rounded-md border border-sidebar-border bg-sidebar-accent/40 px-3 text-sm text-sidebar-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        ) : null}
        <SidebarButton
          active={activeView === 'books'}
          icon={<BookOpen size={18} />}
          label="Biblioteca"
          onClick={onOpenBooks}
        />
        <SidebarButton
          active={activeView === 'chat'}
          icon={<Sparkles size={18} />}
          label="Python Assistant"
          onClick={onOpenAssistant}
        />
        <SidebarButton
          active={activeView === 'settings'}
          icon={<Settings2 size={18} />}
          label="Configurações"
          onClick={onOpenSettings}
        />
      </div>

      <div className="mt-6 min-h-0 flex-1 overflow-y-auto px-3">
        {isLoading ? (
          <div className="space-y-2">
            <div className="h-9 rounded-md bg-sidebar-accent" />
            <div className="h-9 rounded-md bg-sidebar-accent" />
          </div>
        ) : pinnedSessions.length > 0 || groupedSessions.length > 0 ? (
          <>
            {pinnedSessions.length > 0 ? (
              <div className="mb-4">
                <p className="mb-2 px-2 text-sm font-semibold text-foreground">Fixados</p>
                {pinnedSessions.map(renderSessionRow)}
              </div>
            ) : null}

            <p className="mb-2 px-2 text-sm font-semibold text-foreground">Recentes</p>
            {groupedSessions.map(group => (
              <div className="mb-4" key={group.label}>
                <p className="mb-1 px-2 text-xs text-muted-foreground">{group.label}</p>
                {group.items.map(renderSessionRow)}
              </div>
            ))}
          </>
        ) : (
          <p className="px-2 text-sm text-muted-foreground">
            {searchQuery.trim() ? 'Nenhuma conversa encontrada.' : 'Nenhuma conversa ainda.'}
          </p>
        )}
      </div>

      <div className="flex items-center gap-3 border-t border-sidebar-border p-4">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-emerald-500 text-sm font-semibold text-white">
          MS
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">Python Team</p>
          <p className="text-xs text-muted-foreground">Workspace local</p>
        </div>
      </div>
    </div>
  )
}

function SidebarButton({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon: ReactNode
  label: string
  active?: boolean
  onClick?: () => void
}) {
  return (
    <button
      className={cn(
        'flex h-10 w-full items-center gap-3 rounded-md px-2 text-sm text-sidebar-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
        active && 'bg-sidebar-accent text-sidebar-accent-foreground',
      )}
      onClick={onClick}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}
