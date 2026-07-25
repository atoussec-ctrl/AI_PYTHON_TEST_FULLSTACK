import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createBook,
  createSession,
  deleteAttachment,
  deleteSession,
  importBook,
  listBooks,
  listMessages,
  listSessions,
  semanticSearch,
  sendMessage,
  sendMessageWithFiles,
  updateSessionPin,
  uploadAttachment,
} from './client'
import { saveApiCredential } from './credentials'

describe('chat session client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists sessions from API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json([
          {
            id: 'session_1',
            title: 'Conversa',
            pinned: false,
            pinned_at: null,
            created_at: '2026-06-12T00:00:00Z',
            updated_at: '2026-06-12T01:00:00Z',
          },
        ]),
      ),
    )

    const sessions = await listSessions()
    expect(sessions).toHaveLength(1)
    expect(sessions[0].title).toBe('Conversa')
  })

  it('lists messages for a session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json([
          {
            id: 'msg_1',
            session_id: 'session_1',
            role: 'user',
            content: 'Pergunta',
            created_at: '2026-06-12T00:00:00Z',
          },
        ]),
      ),
    )

    const messages = await listMessages('session_1')
    expect(messages[0].content).toBe('Pergunta')
  })

  it('creates a book', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          id: 'book_1',
          title: 'Clean Code',
          author: 'Robert Martin',
          category: 'tech',
          publication_date: '2008-01-01',
          publication_year: 2008,
          summary: 'Princípios de código limpo.',
          created_at: '2026-06-12T00:00:00Z',
        }),
      ),
    )

    const book = await createBook({
      title: 'Clean Code',
      author: 'Robert Martin',
      category: 'tech',
      publication_year: 2008,
      summary: 'Princípios de código limpo.',
    })

    expect(book.id).toBe('book_1')
  })

  it('lists books with optional filters', async () => {
    const fetchMock = vi.fn(async () => Response.json([]))
    vi.stubGlobal('fetch', fetchMock)

    await listBooks({ q: 'python', category: 'tech' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/books?q=python&category=tech'),
      expect.any(Object),
    )
  })

  it('lists books with no filters (no query string)', async () => {
    const fetchMock = vi.fn(async () => Response.json([]))
    vi.stubGlobal('fetch', fetchMock)

    await listBooks()

    // URL should end in /books without a ? when no filters provided
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/books$/),
      expect.any(Object),
    )
  })

  it('sends a chat message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          user_message_id: 'msg_user',
          assistant_message_id: 'msg_1',
          status: 'completed',
          assistant_message: {
            id: 'msg_1',
            session_id: 'session_1',
            role: 'assistant',
            content: 'Olá',
            status: 'completed',
            attachments: [],
            created_at: '2026-06-12T00:00:00Z',
          },
        }),
      ),
    )

    const response = await sendMessage({
      session_id: 'session_1',
      content: 'Oi',
      thinking_mode: 'balanced',
    })

    expect(response.assistant_message.content).toBe('Olá')
  })

  it('sends message fields and files in one multipart request', async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        user_message_id: 'msg_user',
        assistant_message_id: 'msg_assistant',
        status: 'completed',
        assistant_message: {
          id: 'msg_assistant',
          session_id: 'session_1',
          role: 'assistant',
          content: 'Recebido',
          thinking_mode: 'balanced',
          status: 'completed',
          trace_id: null,
          attachments: [],
          created_at: '2026-07-24T00:00:00Z',
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const first = new File(['um'], 'um.txt', { type: 'text/plain' })
    const second = new File(['dois'], 'dois.md', { type: 'text/markdown' })

    await sendMessageWithFiles(
      {
        session_id: 'session_1',
        content: 'Analise os arquivos',
        thinking_mode: 'deep',
        model: 'local-model',
      },
      [
        { file: first, kind: 'document' },
        { file: second, kind: 'document' },
      ],
    )

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    const body = init.body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('session_id')).toBe('session_1')
    expect(body.get('content')).toBe('Analise os arquivos')
    expect(body.get('thinking_mode')).toBe('deep')
    expect(body.get('model')).toBe('local-model')
    expect(body.getAll('files')).toEqual([first, second])
    expect(body.getAll('attachment_kinds')).toEqual(['document', 'document'])
  })

  it('creates a session with default title', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          id: 'session_new',
          title: 'Nova conversa',
          pinned: false,
          pinned_at: null,
          created_at: '2026-06-12T00:00:00Z',
          updated_at: '2026-06-12T00:00:00Z',
        }),
      ),
    )

    const session = await createSession()
    expect(session.id).toBe('session_new')
  })

  it('imports a book from a PDF file', async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        book: {
          id: 'book_2',
          title: 'Extracted Title',
          author: 'AI',
          category: 'tech',
          publication_date: '2024-01-01',
          publication_year: 2024,
          summary: 'Auto-extracted summary.',
        },
        extracted: {
          title: 'Extracted Title',
          category: 'tech',
          author: 'AI',
          publication_year: 2024,
          summary: 'Auto-extracted summary.',
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['%PDF content'], 'book.pdf', { type: 'application/pdf' })
    const result = await importBook(file)

    expect(result.book.id).toBe('book_2')
    // Must be sent as FormData (no Content-Type header override)
    const [, callInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(callInit.body).toBeInstanceOf(FormData)
  })

  it('uploads an attachment with FormData', async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        id: 'att_1',
        filename: 'photo.png',
        mime_type: 'image/png',
        size: 1024,
        kind: 'image',
        url: '/uploads/photo.png',
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['img'], 'photo.png', { type: 'image/png' })
    const attachment = await uploadAttachment('session_1', file, 'image')

    expect(attachment.id).toBe('att_1')
    expect(attachment.kind).toBe('image')

    // Verify FormData was used (no JSON Content-Type)
    const [, callInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(callInit.body).toBeInstanceOf(FormData)
  })

  it('performs a semantic search', async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        results: [
          {
            document_id: 'doc_1',
            title: 'Clean Architecture',
            score: 0.92,
            excerpt: 'Dependency inversion principle...',
          },
        ],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await semanticSearch('dependency injection', 5)

    expect(result.results).toHaveLength(1)
    expect(result.results[0].score).toBe(0.92)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/semantic-search'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('deleteSession', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resolves when API returns 204', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 204 })),
    )

    await expect(deleteSession('session_1')).resolves.toBeUndefined()
  })

  it('throws API error message when delete fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json(
          { error: { message: 'Conversa não encontrada.' } },
          { status: 404 },
        ),
      ),
    )

    await expect(deleteSession('missing')).rejects.toThrow('Conversa não encontrada.')
  })

  it('uses friendly message when "requested URL was not found" error occurs', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json(
          { error: { message: 'The requested URL was not found on the server.' } },
          { status: 404 },
        ),
      ),
    )

    await expect(deleteSession('session_1')).rejects.toThrow(
      'Endpoint da API indisponível',
    )
  })

  it('falls back to generic message when response body is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('Internal Server Error', { status: 500 })),
    )

    await expect(deleteSession('session_1')).rejects.toThrow(
      'Falha ao excluir a conversa.',
    )
  })
})

describe('deleteAttachment', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resolves when the API returns 204', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))

    await expect(deleteAttachment('att_1')).resolves.toBeUndefined()
  })

  it('sends a DELETE request to the attachment endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await deleteAttachment('att_1')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/attachments/att_1'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('throws the API error message when deletion fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({ error: { message: 'Anexo já vinculado a uma mensagem.' } }, { status: 400 }),
      ),
    )

    await expect(deleteAttachment('att_1')).rejects.toThrow('Anexo já vinculado a uma mensagem.')
  })

  it('falls back to a generic message when the error response is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('boom', { status: 500 })))

    await expect(deleteAttachment('att_1')).rejects.toThrow('Falha ao remover anexo.')
  })
})

describe('API key header', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    sessionStorage.clear()
  })

  it('does not send an Authorization header when no runtime credential exists', async () => {
    const fetchMock = vi.fn(async () => Response.json([]))
    vi.stubGlobal('fetch', fetchMock)

    await listSessions()

    const [, callInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((callInit.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('sends a Bearer Authorization header from the browser session', async () => {
    saveApiCredential('test-secret')
    const fetchMock = vi.fn(async () => Response.json([]))
    vi.stubGlobal('fetch', fetchMock)

    await listSessions()

    const [, callInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((callInit.headers as Record<string, string>).Authorization).toBe('Bearer test-secret')
  })

  it('sends the Authorization header on requests using the raw fetch path (deleteSession)', async () => {
    saveApiCredential('test-secret')
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await deleteSession('session_1')

    const [, callInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((callInit.headers as Record<string, string>).Authorization).toBe('Bearer test-secret')
  })
})

describe('updateSessionPin', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('patches pinned state on the session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          id: 'session_1',
          title: 'Conversa',
          pinned: true,
          pinned_at: '2026-06-12T02:00:00Z',
          created_at: '2026-06-12T00:00:00Z',
          updated_at: '2026-06-12T02:00:00Z',
        }),
      ),
    )

    const session = await updateSessionPin('session_1', true)
    expect(session.pinned).toBe(true)
  })

  it('throws friendly error when "URL not found" occurs during generic request', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json(
          { error: { message: 'The requested URL was not found on the server.' } },
          { status: 404 },
        ),
      ),
    )

    await expect(updateSessionPin('session_x', false)).rejects.toThrow(
      'Endpoint da API indisponível',
    )
  })
})
