import { ChevronDown, Menu, Moon, Sun, X } from 'lucide-react'

import type { AppTheme } from '@/app/types'
import { Button } from '@/components/ui/button'
import type { ThinkingMode } from '@/shared/api/types'
import { MODEL_OPTIONS, THINKING_OPTIONS, type ChatModel } from './config'

interface ChatHeaderProps {
  title: string
  model: ChatModel
  thinkingMode: ThinkingMode
  theme: AppTheme
  isMobileSidebarOpen: boolean
  onToggleSidebar: () => void
  onModelChange: (model: ChatModel) => void
  onThinkingChange: (mode: ThinkingMode) => void
  onThemeToggle: () => void
}

export function ChatHeader({
  title,
  model,
  thinkingMode,
  theme,
  isMobileSidebarOpen,
  onToggleSidebar,
  onModelChange,
  onThinkingChange,
  onThemeToggle,
}: ChatHeaderProps) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border px-3 sm:px-5">
      <div className="flex min-w-0 items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label={isMobileSidebarOpen ? 'Fechar menu' : 'Abrir menu'}
          onClick={onToggleSidebar}
        >
          {isMobileSidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold">{title}</h1>
          <p className="hidden text-xs text-muted-foreground sm:block">
            Assistente para Python, Flask, testes e arquitetura
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <label className="hidden items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm sm:flex">
          <span className="text-muted-foreground">Modelo</span>
          <select
            className="bg-transparent outline-none"
            value={model}
            onChange={event => onModelChange(event.target.value as ChatModel)}
          >
            {MODEL_OPTIONS.map(option => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <ChevronDown size={14} />
        </label>

        <label className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm">
          <span className="hidden text-muted-foreground sm:inline">Thinking</span>
          <select
            className="bg-transparent outline-none"
            value={thinkingMode}
            onChange={event => onThinkingChange(event.target.value as ThinkingMode)}
          >
            {THINKING_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <Button
          variant="ghost"
          size="icon"
          aria-label="Alternar tema"
          onClick={onThemeToggle}
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </Button>
      </div>
    </header>
  )
}
