import { afterEach, describe, expect, it, vi } from 'vitest'

import { sendMessageWithAttachments } from './sendMessageWithAttachments'

import * as client from '@/shared/api/client'

import type { PendingAttachment } from './attachments'
import type { SendMessageResponse } from '@/shared/api/types'

function pendingAttachment(id: string): PendingAttachment {
  return {
    id,
    file: new File(['conteudo'], `${id}.txt`),
    kind: 'document',
  }
}

const sendMessageResponse: SendMessageResponse = {
  user_message_id: 'msg_user',
  assistant_message_id: 'msg_assistant',
  status: 'completed',
  assistant_message: {
    id: 'msg_assistant',
    session_id: 'session_1',
    role: 'assistant',
    content: 'Olá',
    thinking_mode: 'balanced',
    status: 'completed',
    trace_id: null,
    attachments: [],
    created_at: '2026-07-21T00:00:00Z',
  },
}

describe('sendMessageWithAttachments', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sends the message directly as JSON when there are no attachments', async () => {
    const sendMessage = vi.spyOn(client, 'sendMessage').mockResolvedValue(sendMessageResponse)
    const sendMessageWithFiles = vi.spyOn(client, 'sendMessageWithFiles')

    const result = await sendMessageWithAttachments({
      sessionId: 'session_1',
      content: 'oi',
      thinkingMode: 'balanced',
      attachments: [],
    })

    expect(result).toBe(sendMessageResponse)
    expect(sendMessageWithFiles).not.toHaveBeenCalled()
    expect(sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ session_id: 'session_1', content: 'oi', attachment_ids: [] }),
      undefined,
    )
  })

  it('sends every pending attachment in one atomic multipart request', async () => {
    const sendMessage = vi.spyOn(client, 'sendMessage')
    const sendMessageWithFiles = vi
      .spyOn(client, 'sendMessageWithFiles')
      .mockResolvedValue(sendMessageResponse)
    const attachments = [pendingAttachment('local_1'), pendingAttachment('local_2')]

    const result = await sendMessageWithAttachments({
      sessionId: 'session_1',
      content: 'veja os anexos',
      thinkingMode: 'balanced',
      attachments,
    })

    expect(result).toBe(sendMessageResponse)
    expect(sendMessage).not.toHaveBeenCalled()
    expect(sendMessageWithFiles).toHaveBeenCalledWith(
      expect.objectContaining({
        session_id: 'session_1',
        content: 'veja os anexos',
        thinking_mode: 'balanced',
      }),
      attachments,
      undefined,
    )
  })

  it('propagates an atomic failure without issuing client-side cleanup calls', async () => {
    const sendError = new Error('Falha ao enviar mensagem.')
    vi.spyOn(client, 'sendMessageWithFiles').mockRejectedValue(sendError)
    const deleteAttachment = vi.spyOn(client, 'deleteAttachment')

    await expect(
      sendMessageWithAttachments({
        sessionId: 'session_1',
        content: 'vai falhar',
        thinkingMode: 'balanced',
        attachments: [pendingAttachment('local_1')],
      }),
    ).rejects.toThrow(sendError)

    expect(deleteAttachment).not.toHaveBeenCalled()
  })
})
