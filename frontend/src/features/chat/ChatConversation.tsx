import { Suspense, lazy, type RefObject } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Bot, Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { ChatMessage, ThinkingMode } from '@/shared/api/types'
import { cn } from '@/shared/lib/utils'
import type { PendingAttachment } from './attachments'
import { SUGGESTIONS, thinkingModeLabel } from './config'
import { ThinkingIndicator } from './ThinkingIndicator'

const AssistantMarkdown = lazy(() => import('./AssistantMarkdown'))

export interface OptimisticTurn {
  userContent: string
  attachments: PendingAttachment[]
  thinkingMode: ThinkingMode
}

interface ChatConversationProps {
  isLoading: boolean
  hasSelectedSession: boolean
  messages: ChatMessage[]
  optimisticTurn: OptimisticTurn | null
  isSending: boolean
  messagesEndRef: RefObject<HTMLDivElement | null>
  onUseSuggestion: (suggestion: string) => void
}

export function ChatConversation({
  isLoading,
  hasSelectedSession,
  messages,
  optimisticTurn,
  isSending,
  messagesEndRef,
  onUseSuggestion,
}: ChatConversationProps) {
  return (
    <div className="h-full overflow-y-auto px-4 pb-[180px] pt-8 sm:px-8">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-8">
        {isLoading && hasSelectedSession && !optimisticTurn ? (
          <MessageSkeleton />
        ) : messages.length > 0 || optimisticTurn ? (
          <>
            <MessageList messages={messages} />
            {optimisticTurn && (
              <>
                <OptimisticUserBubble turn={optimisticTurn} />
                <AnimatePresence>
                  {isSending && (
                    <ThinkingIndicator
                      modeLabel={thinkingModeLabel(optimisticTurn.thinkingMode)}
                    />
                  )}
                </AnimatePresence>
              </>
            )}
            <div ref={messagesEndRef} />
          </>
        ) : (
          <EmptyState onUseSuggestion={onUseSuggestion} />
        )}
      </div>
    </div>
  )
}

function EmptyState({ onUseSuggestion }: { onUseSuggestion: (value: string) => void }) {
  return (
    <motion.div
      className="mx-auto flex min-h-[56vh] max-w-3xl flex-col items-center justify-center text-center"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="mb-5 grid h-14 w-14 place-items-center rounded-xl border border-border bg-secondary">
        <Sparkles size={24} />
      </div>
      <h2 className="text-2xl font-semibold sm:text-3xl">Como posso ajudar com Python?</h2>
      <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground sm:text-base">
        Envie uma pergunta, erro, arquivo de código, imagem ou áudio. O assistente
        responde em português com foco em boas práticas.
      </p>
      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map(suggestion => (
          <button
            key={suggestion}
            className="rounded-lg border border-border bg-card px-4 py-3 text-left text-sm transition hover:bg-accent"
            onClick={() => onUseSuggestion(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </motion.div>
  )
}

function OptimisticUserBubble({ turn }: { turn: OptimisticTurn }) {
  return (
    <motion.article
      className="flex w-full justify-end"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
    >
      <div className="max-w-[860px] rounded-2xl bg-secondary px-5 py-4 text-secondary-foreground sm:max-w-[72%]">
        {turn.attachments.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {turn.attachments.map(attachment => (
              <Badge key={attachment.id}>{attachment.file.name}</Badge>
            ))}
          </div>
        )}
        {turn.userContent ? (
          <p className="whitespace-pre-wrap text-base leading-7">{turn.userContent}</p>
        ) : (
          <p className="text-sm text-muted-foreground">Enviando anexos...</p>
        )}
      </div>
    </motion.article>
  )
}

function MessageList({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="space-y-8" aria-live="polite">
      {messages.map(message => (
        <motion.article
          key={message.id}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
        >
          <MessageBubble message={message} />
        </motion.article>
      ))}
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'group relative max-w-[860px]',
          isUser
            ? 'rounded-2xl bg-secondary px-5 py-4 text-secondary-foreground sm:max-w-[72%]'
            : 'w-full text-foreground',
        )}
      >
        {!isUser && (
          <div className="mb-3 flex items-center gap-2 text-sm font-medium">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground">
              <Bot size={16} />
            </span>
            MindSight AI
            {message.thinking_mode && (
              <Badge>{thinkingModeLabel(message.thinking_mode)}</Badge>
            )}
          </div>
        )}

        {message.attachments.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {message.attachments.map(attachment => (
              <Badge key={attachment.id}>{attachment.filename}</Badge>
            ))}
          </div>
        )}

        <div className={cn(!isUser && 'prose-chat max-w-none')}>
          {isUser ? (
            <p className="whitespace-pre-wrap text-base leading-7">{message.content}</p>
          ) : (
            <Suspense
              fallback={
                <p className="text-sm text-muted-foreground">Carregando resposta...</p>
              }
            >
              <AssistantMarkdown content={message.content} />
            </Suspense>
          )}
        </div>
      </div>
    </div>
  )
}

function MessageSkeleton() {
  return (
    <div className="space-y-8">
      <div className="ml-auto h-24 max-w-[70%] rounded-2xl bg-secondary animate-shimmer" />
      <div className="h-44 rounded-lg bg-secondary animate-shimmer" />
    </div>
  )
}
