import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { resolveTheme, type AppTheme, type AppView } from '@/app/types'
import { BooksAdminView } from '@/features/books/BooksAdminView'
import {
  type PendingAttachment,
  revokePendingAttachment,
  validateFiles,
} from '@/features/chat/attachments'
import { ChatComposer } from '@/features/chat/ChatComposer'
import {
  ChatConversation,
  type OptimisticTurn,
} from '@/features/chat/ChatConversation'
import {
  DEFAULT_CHAT_MODEL,
  resolveThinkingMode,
  type ChatModel,
} from '@/features/chat/config'
import { ChatHeader } from '@/features/chat/ChatHeader'
import { ChatSidebar } from '@/features/chat/ChatSidebar'
import { sendMessageWithAttachments } from '@/features/chat/sendMessageWithAttachments'
import { useAudioRecorder } from '@/features/chat/useAudioRecorder'
import { SettingsView } from '@/features/settings/SettingsView'
import { useDialogAccessibility } from '@/hooks/useDialogAccessibility'
import { useHandleMobileSideBar } from '@/hooks/useHandleMobileSideBar'
import {
  createSession,
  deleteSession,
  listMessages,
  listSessions,
  sendMessage,
  updateSessionPin,
} from '@/shared/api/client'
import type { Book, ThinkingMode } from '@/shared/api/types'
import {
  filterSessionsByQuery,
  groupSessionsForSidebar,
} from '@/shared/lib/utils'

interface SendMessagePayload {
  content: string
  attachments: PendingAttachment[]
}

function isAbortError(error: unknown): boolean {
  return (
    error instanceof DOMException &&
    (error.name === 'AbortError' || error.code === 20)
  )
}

function App() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const pendingAttachmentsRef = useRef<PendingAttachment[]>([])
  const inFlightAttachmentsRef = useRef<PendingAttachment[]>([])

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [composerValue, setComposerValue] = useState('')
  const [optimisticTurn, setOptimisticTurn] = useState<OptimisticTurn | null>(null)
  const [thinkingMode, setThinkingMode] = useState<ThinkingMode>(() =>
    resolveThinkingMode(import.meta.env.VITE_DEFAULT_THINKING_MODE),
  )
  const [model, setModel] = useState<ChatModel>(DEFAULT_CHAT_MODEL)
  const [theme, setTheme] = useState<AppTheme>(() =>
    resolveTheme(localStorage.getItem('mindsight-theme')),
  )
  const [activeView, setActiveView] = useState<AppView>('chat')
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([])
  const [uiError, setUiError] = useState<string | null>(null)

  const mobileSidebar = useHandleMobileSideBar()
  const mobileDrawerRef = useDialogAccessibility<HTMLElement>(
    mobileSidebar.isOpen,
    mobileSidebar.handleClose,
  )
  const audioRecorder = useAudioRecorder()

  const sessionsQuery = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
  })

  const messagesQuery = useQuery({
    queryKey: ['messages', selectedSessionId],
    queryFn: () => listMessages(selectedSessionId as string),
    enabled: Boolean(selectedSessionId),
  })

  const sendMessageMutation = useMutation({
    mutationFn: async ({ content, attachments }: SendMessagePayload) => {
      const signal = abortControllerRef.current?.signal
      const trimmed = content.trim()
      if (!trimmed && attachments.length === 0) {
        throw new Error('Digite uma pergunta ou anexe um arquivo.')
      }

      let session = selectedSessionId
      if (!session) {
        session = (
          await createSession(trimmed ? trimmed.slice(0, 54) : 'Conversa com anexos')
        ).id
        setSelectedSessionId(session)
        queryClient.invalidateQueries({ queryKey: ['sessions'] })
      }

      return sendMessageWithAttachments({
        sessionId: session,
        content: trimmed,
        thinkingMode,
        attachments,
        model,
        signal,
      })
    },
    onMutate: ({ content, attachments }) => {
      abortControllerRef.current = new AbortController()
      inFlightAttachmentsRef.current = [...attachments]
      setOptimisticTurn({
        userContent: content.trim(),
        attachments: [...attachments],
        thinkingMode,
      })
      setComposerValue('')
      setPendingAttachments([])
      setUiError(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    },
    onSuccess: (response, variables) => {
      variables.attachments.forEach(revokePendingAttachment)
      inFlightAttachmentsRef.current = []
      setOptimisticTurn(null)
      setSelectedSessionId(response.assistant_message.session_id)
      setUiError(null)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      queryClient.invalidateQueries({
        queryKey: ['messages', response.assistant_message.session_id],
      })
    },
    onError: (error, variables) => {
      inFlightAttachmentsRef.current = []
      setOptimisticTurn(null)
      setComposerValue(variables.content)
      setPendingAttachments(variables.attachments)
      if (isAbortError(error)) {
        setUiError(null)
        return
      }
      setUiError(error instanceof Error ? error.message : 'Falha ao enviar mensagem.')
    },
    onSettled: () => {
      abortControllerRef.current = null
    },
  })

  const askBookMutation = useMutation({
    mutationFn: async (book: Book) => {
      const session = await createSession(`Livro: ${book.title}`.slice(0, 64))
      return sendMessage({
        session_id: session.id,
        content: `Resuma o livro "${book.title}", cite autor, data de publicação e explique os pontos principais usando somente a biblioteca local.`,
        thinking_mode: 'deep',
        model,
      })
    },
    onSuccess: response => {
      setActiveView('chat')
      setSelectedSessionId(response.assistant_message.session_id)
      setUiError(null)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      queryClient.invalidateQueries({
        queryKey: ['messages', response.assistant_message.session_id],
      })
    },
    onError: error => {
      setUiError(error instanceof Error ? error.message : 'Falha ao consultar a IA.')
    },
  })

  const deleteSessionMutation = useMutation({
    mutationFn: deleteSession,
    onSuccess: (_data, deletedId) => {
      if (selectedSessionId === deletedId) {
        setSelectedSessionId(null)
        setComposerValue('')
      }
      setUiError(null)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      queryClient.removeQueries({ queryKey: ['messages', deletedId] })
    },
    onError: error => {
      setUiError(error instanceof Error ? error.message : 'Falha ao excluir conversa.')
    },
  })

  const pinSessionMutation = useMutation({
    mutationFn: ({ sessionId, pinned }: { sessionId: string; pinned: boolean }) =>
      updateSessionPin(sessionId, pinned),
    onSuccess: () => {
      setUiError(null)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
    onError: error => {
      setUiError(error instanceof Error ? error.message : 'Falha ao fixar conversa.')
    },
  })

  const sessions = useMemo(() => sessionsQuery.data ?? [], [sessionsQuery.data])
  const messages = messagesQuery.data ?? []
  const [sessionSearchQuery, setSessionSearchQuery] = useState('')
  const { pinned: pinnedSessions, groups: groupedSessions } = useMemo(
    () => groupSessionsForSidebar(filterSessionsByQuery(sessions, sessionSearchQuery)),
    [sessions, sessionSearchQuery],
  )
  const selectedSession = sessions.find(session => session.id === selectedSessionId)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('mindsight-theme', theme)
  }, [theme])

  useEffect(() => {
    pendingAttachmentsRef.current = pendingAttachments
  }, [pendingAttachments])

  useEffect(() => {
    return () => {
      pendingAttachmentsRef.current.forEach(revokePendingAttachment)
      inFlightAttachmentsRef.current.forEach(revokePendingAttachment)
    }
  }, [])

  useEffect(() => {
    if (!sendMessageMutation.isPending && !optimisticTurn) {
      return
    }
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [sendMessageMutation.isPending, optimisticTurn, messages.length])

  function selectFiles(files: FileList | null) {
    if (!files) return
    const result = validateFiles(Array.from(files), pendingAttachments.length)
    setPendingAttachments(current => [...current, ...result.accepted])
    setUiError(result.errors[0] ?? null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  function removeAttachment(id: string) {
    setPendingAttachments(current => {
      const target = current.find(item => item.id === id)
      if (target) revokePendingAttachment(target)
      return current.filter(item => item.id !== id)
    })
  }

  async function toggleRecording() {
    try {
      if (audioRecorder.isRecording) {
        const file = await audioRecorder.stop()
        const result = validateFiles([file], pendingAttachments.length)
        setPendingAttachments(current => [...current, ...result.accepted])
        setUiError(result.errors[0] ?? null)
      } else {
        await audioRecorder.start()
        setUiError(null)
      }
    } catch (error) {
      setUiError(
        error instanceof Error
          ? error.message
          : 'Não foi possível acessar o microfone.',
      )
    }
  }

  function submit() {
    if (sendMessageMutation.isPending) {
      return
    }

    const content = composerValue.trim()
    if (!content && pendingAttachments.length === 0) {
      setUiError('Digite uma pergunta ou anexe um arquivo.')
      return
    }

    sendMessageMutation.mutate({
      content,
      attachments: [...pendingAttachments],
    })
  }

  function stopGeneration() {
    abortControllerRef.current?.abort()
  }

  const sidebar = (
    <ChatSidebar
      pinnedSessions={pinnedSessions}
      groupedSessions={groupedSessions}
      selectedSessionId={selectedSessionId}
      isLoading={sessionsQuery.isLoading}
      searchQuery={sessionSearchQuery}
      onSearchQueryChange={setSessionSearchQuery}
      onNewChat={() => {
        setActiveView('chat')
        setSelectedSessionId(null)
        setComposerValue('')
        mobileSidebar.handleClose()
      }}
      activeView={activeView}
      onCloseSidebar={mobileSidebar.handleClose}
      onOpenBooks={() => {
        setActiveView('books')
        mobileSidebar.handleClose()
      }}
      onOpenAssistant={() => {
        setActiveView('chat')
        mobileSidebar.handleClose()
      }}
      onOpenSettings={() => {
        setActiveView('settings')
        mobileSidebar.handleClose()
      }}
      onSelectSession={sessionId => {
        setActiveView('chat')
        setSelectedSessionId(sessionId)
        mobileSidebar.handleClose()
      }}
      onDeleteSession={sessionId => deleteSessionMutation.mutateAsync(sessionId)}
      onPinSession={(sessionId, pinned) =>
        pinSessionMutation.mutateAsync({ sessionId, pinned })
      }
      isDeletingSession={deleteSessionMutation.isPending}
      isPinningSession={pinSessionMutation.isPending}
    />
  )

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <div className="flex h-dvh overflow-hidden">
        <aside className="hidden w-[326px] shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:block">
          {sidebar}
        </aside>

        <AnimatePresence>
          {mobileSidebar.isOpen && (
            <motion.div
              className="fixed inset-0 z-40 bg-black/45 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={mobileSidebar.handleClose}
            >
              <motion.aside
                ref={mobileDrawerRef}
                role="dialog"
                aria-modal="true"
                aria-label="Menu de navegação"
                tabIndex={-1}
                className="h-full w-[82vw] max-w-[326px] border-r border-sidebar-border bg-sidebar text-sidebar-foreground outline-none"
                initial={{ x: -340 }}
                animate={{ x: 0 }}
                exit={{ x: -340 }}
                transition={{ type: 'spring', damping: 28, stiffness: 260 }}
                onClick={event => event.stopPropagation()}
              >
                {sidebar}
              </motion.aside>
            </motion.div>
          )}
        </AnimatePresence>

        <main className="flex min-w-0 flex-1 flex-col bg-background">
          <ChatHeader
            title={
              activeView === 'books'
                ? 'Biblioteca de livros'
                : activeView === 'settings'
                  ? 'Configurações'
                  : selectedSession?.title ?? 'MindSight AI'
            }
            model={model}
            thinkingMode={thinkingMode}
            theme={theme}
            isMobileSidebarOpen={mobileSidebar.isOpen}
            onToggleSidebar={mobileSidebar.handleOpen}
            onModelChange={setModel}
            onThinkingChange={setThinkingMode}
            onThemeToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          />

          {activeView === 'books' ? (
            <BooksAdminView
              actionError={uiError}
              isAskingBook={askBookMutation.isPending}
              onAskBook={book => askBookMutation.mutate(book)}
            />
          ) : activeView === 'settings' ? (
            <SettingsView
              theme={theme}
              model={model}
              thinkingMode={thinkingMode}
              onThemeToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              onModelChange={setModel}
              onThinkingChange={setThinkingMode}
            />
          ) : (
            <section className="relative min-h-0 flex-1">
              <ChatConversation
                isLoading={messagesQuery.isLoading}
                hasSelectedSession={Boolean(selectedSessionId)}
                messages={messages}
                optimisticTurn={optimisticTurn}
                isSending={sendMessageMutation.isPending}
                messagesEndRef={messagesEndRef}
                onUseSuggestion={setComposerValue}
              />

              <ChatComposer
                value={composerValue}
                thinkingMode={thinkingMode}
                model={model}
                attachments={pendingAttachments}
                error={uiError}
                isSending={sendMessageMutation.isPending}
                isRecording={audioRecorder.isRecording}
                onChange={setComposerValue}
                onSubmit={submit}
                onStop={stopGeneration}
                onAttachClick={() => fileInputRef.current?.click()}
                onRemoveAttachment={removeAttachment}
                onToggleRecording={toggleRecording}
              />

              <input
                ref={fileInputRef}
                className="hidden"
                type="file"
                multiple
                accept=".txt,.md,.py,.json,.pdf,.png,.jpg,.jpeg,.webp,.webm,.wav,.mp3"
                disabled={sendMessageMutation.isPending}
                onChange={event => selectFiles(event.target.files)}
              />
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
