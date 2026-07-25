import { sendMessage, sendMessageWithFiles } from '@/shared/api/client'

import type { PendingAttachment } from './attachments'
import type { SendMessageResponse, ThinkingMode } from '@/shared/api/types'

interface SendMessageWithAttachmentsInput {
  sessionId: string
  content: string
  thinkingMode: ThinkingMode | string
  attachments: PendingAttachment[]
  model?: string
  signal?: AbortSignal
}

/**
 * Sends files and message fields through the backend's atomic multipart path.
 * Requests without files stay JSON to keep the common path compact.
 */
export function sendMessageWithAttachments({
  sessionId,
  content,
  thinkingMode,
  attachments,
  model,
  signal,
}: SendMessageWithAttachmentsInput): Promise<SendMessageResponse> {
  const message = {
    session_id: sessionId,
    content,
    thinking_mode: thinkingMode as ThinkingMode,
    model,
  }
  if (attachments.length === 0) {
    return sendMessage({ ...message, attachment_ids: [] }, signal)
  }
  return sendMessageWithFiles(message, attachments, signal)
}
