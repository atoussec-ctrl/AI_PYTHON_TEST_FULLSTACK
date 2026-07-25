import { AnimatePresence, motion } from 'framer-motion'
import {
  FileAudio,
  FileCode2,
  FileText,
  ImageIcon,
  Mic,
  Paperclip,
  SendHorizontal,
  Square,
  X,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { AttachmentKind, ThinkingMode } from '@/shared/api/types'
import { formatFileSize } from '@/shared/lib/utils'
import type { PendingAttachment } from './attachments'
import { thinkingModeLabel } from './config'

interface ChatComposerProps {
  value: string
  thinkingMode: ThinkingMode
  model: string
  attachments: PendingAttachment[]
  error: string | null
  isSending: boolean
  isRecording: boolean
  onChange: (value: string) => void
  onSubmit: () => void
  onStop: () => void
  onAttachClick: () => void
  onRemoveAttachment: (id: string) => void
  onToggleRecording: () => void
}

export function ChatComposer({
  value,
  thinkingMode,
  model,
  attachments,
  error,
  isSending,
  isRecording,
  onChange,
  onSubmit,
  onStop,
  onAttachClick,
  onRemoveAttachment,
  onToggleRecording,
}: ChatComposerProps) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-background via-background to-background/0 px-3 pb-3 pt-10 sm:px-6">
      <div className="pointer-events-auto mx-auto w-full max-w-[960px]">
        <AnimatePresence>
          {attachments.length > 0 && (
            <motion.div
              className="mb-2 flex gap-2 overflow-x-auto"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
            >
              {attachments.map(attachment => (
                <AttachmentPreview
                  key={attachment.id}
                  attachment={attachment}
                  onRemove={() => onRemoveAttachment(attachment.id)}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <div
            className="mb-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            role="alert"
          >
            {error}
          </div>
        )}

        <div className="rounded-2xl border border-border bg-composer text-composer-foreground shadow-[0_12px_45px_rgba(0,0,0,0.12)]">
          <Textarea
            value={value}
            placeholder="Pergunte alguma coisa"
            rows={1}
            className="max-h-44 px-5 pt-4"
            onChange={event => onChange(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                onSubmit()
              }
            }}
          />
          <div className="flex items-center justify-between gap-2 px-3 pb-3">
            <div className="flex min-w-0 items-center gap-2">
              <Button
                variant="soft"
                size="icon"
                aria-label="Anexar arquivo"
                disabled={isSending}
                onClick={onAttachClick}
              >
                <Paperclip size={18} />
              </Button>
              <Badge className="hidden max-w-[220px] truncate sm:inline-flex">
                {model}
              </Badge>
              <Badge>{thinkingModeLabel(thinkingMode)}</Badge>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant={isRecording ? 'danger' : 'soft'}
                size="icon"
                aria-label={isRecording ? 'Parar gravação' : 'Gravar áudio'}
                className={isRecording ? 'animate-pulse-recording' : undefined}
                disabled={isSending}
                onClick={onToggleRecording}
              >
                {isRecording ? <Square size={16} /> : <Mic size={18} />}
              </Button>
              <Button
                variant={isSending ? 'danger' : 'default'}
                size="icon"
                aria-label={isSending ? 'Parar geração' : 'Enviar mensagem'}
                onClick={isSending ? onStop : onSubmit}
              >
                {isSending ? <Square size={16} /> : <SendHorizontal size={18} />}
              </Button>
            </div>
          </div>
        </div>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          O MindSight pode cometer erros. Confira informações relevantes.
        </p>
      </div>
    </div>
  )
}

function AttachmentPreview({
  attachment,
  onRemove,
}: {
  attachment: PendingAttachment
  onRemove: () => void
}) {
  return (
    <div className="flex min-w-[210px] items-center gap-3 rounded-lg border border-border bg-card p-2 shadow-sm">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-secondary">
        {attachment.kind === 'image' && attachment.previewUrl ? (
          <img
            src={attachment.previewUrl}
            alt=""
            className="h-full w-full rounded-md object-cover"
          />
        ) : (
          <AttachmentIcon kind={attachment.kind} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{attachment.file.name}</p>
        <p className="text-xs text-muted-foreground">
          {attachment.kind} · {formatFileSize(attachment.file.size)}
        </p>
      </div>
      <Button variant="ghost" size="icon" aria-label="Remover anexo" onClick={onRemove}>
        <X size={16} />
      </Button>
    </div>
  )
}

function AttachmentIcon({ kind }: { kind: AttachmentKind }) {
  if (kind === 'image') return <ImageIcon size={18} />
  if (kind === 'audio') return <FileAudio size={18} />
  if (kind === 'document') return <FileText size={18} />
  return <FileCode2 size={18} />
}
