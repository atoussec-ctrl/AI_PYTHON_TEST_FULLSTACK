import type {
  Attachment,
  AttachmentKind,
  Book,
  ChatMessage,
  ChatSession,
  CreateBookInput,
  ImportBookResponse,
  SemanticSearchResult,
  SendMessageInput,
  SendMessageResponse,
} from './types'
import { readApiCredential } from './credentials'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5000/api/v1'

function parseApiError(
  payload: { error?: { message?: string } } | null,
  fallback: string,
): string {
  const message = payload?.error?.message ?? fallback
  if (message.includes('requested URL was not found')) {
    return 'Endpoint da API indisponível. Reconstrua o backend (docker compose build backend).'
  }
  return message
}

// Mirrors the backend's optional shared-secret gate (app/security.py).
// The key is supplied at runtime and never through a VITE_* build variable:
// Vite variables are public bundle contents, not a place for secrets.
function authHeaders(): HeadersInit {
  const apiKey = readApiCredential()
  return apiKey ? { Authorization: `Bearer ${apiKey}` } : {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...authHeaders(),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiError(payload, 'Falha ao comunicar com a API.'))
  }

  return response.json() as Promise<T>
}

export function listSessions() {
  return request<ChatSession[]>('/chat/sessions')
}

export function listBooks(
  filters: { q?: string; title?: string; author?: string; category?: string } = {},
) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value?.trim()) {
      params.set(key, value.trim())
    }
  }
  const query = params.toString()
  return request<Book[]>(`/books${query ? `?${query}` : ''}`)
}

export function createBook(input: CreateBookInput) {
  return request<Book>('/books', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function importBook(file: File) {
  const formData = new FormData()
  formData.set('file', file)

  return request<ImportBookResponse>('/books/import', {
    method: 'POST',
    body: formData,
  })
}

export function createSession(title = 'Nova conversa') {
  return request<ChatSession>('/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiError(payload, 'Falha ao excluir a conversa.'))
  }
}

export function updateSessionPin(sessionId: string, pinned: boolean) {
  return request<ChatSession>(`/chat/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ pinned }),
  })
}

export function listMessages(sessionId: string) {
  return request<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`)
}

export function sendMessage(input: SendMessageInput, signal?: AbortSignal) {
  return request<SendMessageResponse>('/chat/messages', {
    method: 'POST',
    body: JSON.stringify(input),
    signal,
  })
}

export function sendMessageWithFiles(
  input: SendMessageInput,
  attachments: Array<{ file: File; kind: AttachmentKind }>,
  signal?: AbortSignal,
) {
  const formData = new FormData()
  formData.set('session_id', input.session_id)
  formData.set('content', input.content ?? '')
  formData.set('thinking_mode', input.thinking_mode)
  if (input.model) {
    formData.set('model', input.model)
  }
  for (const attachment of attachments) {
    formData.append('files', attachment.file)
    formData.append('attachment_kinds', attachment.kind)
  }

  return request<SendMessageResponse>('/chat/messages', {
    method: 'POST',
    body: formData,
    signal,
  })
}

export function uploadAttachment(
  sessionId: string,
  file: File,
  kind: AttachmentKind,
  signal?: AbortSignal,
) {
  const formData = new FormData()
  formData.set('session_id', sessionId)
  formData.set('kind', kind)
  formData.set('file', file)

  return request<Attachment>('/attachments', {
    method: 'POST',
    body: formData,
    signal,
  })
}

export async function deleteAttachment(attachmentId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/attachments/${attachmentId}`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiError(payload, 'Falha ao remover anexo.'))
  }
}

export function semanticSearch(query: string, k = 3) {
  return request<{ results: SemanticSearchResult[] }>('/semantic-search', {
    method: 'POST',
    body: JSON.stringify({ query, k }),
  })
}
