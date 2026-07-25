import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/books')) {
        return Response.json([])
      }
      if (url.includes('/chat/sessions')) {
        return Response.json([])
      }
      return Response.json([])
    }),
  )
})

it('toggles the mobile sidebar from the header and closes from the drawer icon', async () => {
  renderApp()

  fireEvent.click(await screen.findByRole('button', { name: 'Abrir menu' }))
  expect(screen.getAllByRole('button', { name: 'Fechar menu' }).length).toBeGreaterThan(0)

  fireEvent.click(screen.getAllByRole('button', { name: 'Fechar menu' }).at(-1)!)

  expect(await screen.findByRole('button', { name: 'Abrir menu' })).toBeInTheDocument()
})

it('exposes the mobile drawer as an accessible dialog and closes it with Escape', async () => {
  renderApp()

  fireEvent.click(await screen.findByRole('button', { name: 'Abrir menu' }))
  const dialog = await screen.findByRole('dialog', { name: 'Menu de navegação' })
  expect(dialog).toBeInTheDocument()

  fireEvent.keyDown(document, { key: 'Escape' })

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(await screen.findByRole('button', { name: 'Abrir menu' })).toBeInTheDocument()
})

it('filters the session list by title through the sidebar search', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/chat/sessions')) {
        return Response.json([
          {
            id: 'session_flask',
            title: 'Dúvida sobre Flask',
            pinned: false,
            pinned_at: null,
            created_at: '2026-06-12T00:00:00Z',
            updated_at: '2026-06-12T01:00:00Z',
          },
          {
            id: 'session_python',
            title: 'Listas em Python',
            pinned: false,
            pinned_at: null,
            created_at: '2026-06-11T00:00:00Z',
            updated_at: '2026-06-11T01:00:00Z',
          },
        ])
      }
      return Response.json([])
    }),
  )

  renderApp()

  expect(await screen.findByText('Dúvida sobre Flask')).toBeInTheDocument()
  expect(screen.getByText('Listas em Python')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Buscar chats' }))
  fireEvent.change(screen.getByLabelText('Buscar chats'), { target: { value: 'flask' } })

  expect(await screen.findByText('Dúvida sobre Flask')).toBeInTheDocument()
  expect(screen.queryByText('Listas em Python')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Buscar chats' }))
  expect(screen.queryByLabelText('Buscar chats')).not.toBeInTheDocument()
  expect(await screen.findByText('Listas em Python')).toBeInTheDocument()
})

it('renders the chat shell and composer', async () => {
  renderApp()

  expect(await screen.findByText('MindSight AI')).toBeInTheDocument()
  expect(screen.getByPlaceholderText('Pergunte alguma coisa')).toBeInTheDocument()
  expect(screen.getByLabelText('Anexar arquivo')).toBeInTheDocument()
})

it('renders the book administration screen', async () => {
  renderApp()

  fireEvent.click(await screen.findByRole('button', { name: 'Biblioteca' }))

  expect(await screen.findByText('Administração')).toBeInTheDocument()
  expect(screen.getByLabelText('Upload de livro')).toBeInTheDocument()
  expect(screen.getByLabelText('Buscar livros')).toBeInTheDocument()
})

it('opens the settings screen with theme, model and thinking controls', async () => {
  renderApp()

  fireEvent.click(await screen.findByRole('button', { name: 'Configurações' }))

  expect(await screen.findByText('Aparência')).toBeInTheDocument()
  expect(screen.getByLabelText('Modelo padrão')).toHaveValue(
    'deepseek-ai/DeepSeek-V4-Flash',
  )
  expect(screen.getByLabelText('Modo de raciocínio padrão')).toBeInTheDocument()
  expect(screen.getByLabelText('Alternar tema nas configurações')).toBeInTheDocument()
})

it('navigates back to chat through the Python Assistant tab', async () => {
  renderApp()

  fireEvent.click(await screen.findByRole('button', { name: 'Biblioteca' }))
  expect(await screen.findByText('Administração')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Python Assistant' }))
  expect(await screen.findByPlaceholderText('Pergunte alguma coisa')).toBeInTheDocument()
})

it('filters books by category and switches to carousel layout', async () => {
  const books = [
    {
      id: 'book_1',
      title: 'Python Fluente',
      category: 'Programação',
      author: 'Luciano Ramalho',
      publication_date: '2015-01-01',
      publication_year: 2015,
      summary: 'Python idiomático.',
    },
    {
      id: 'book_2',
      title: 'Dom Casmurro',
      category: 'Romance',
      author: 'Machado de Assis',
      publication_date: '1899-01-01',
      publication_year: 1899,
      summary: 'Bentinho e Capitu.',
    },
  ]

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/books')) {
        const params = new URL(url).searchParams
        const category = params.get('category')
        return Response.json(
          category ? books.filter(book => book.category === category) : books,
        )
      }
      return Response.json([])
    }),
  )

  renderApp()

  fireEvent.click(await screen.findByRole('button', { name: 'Biblioteca' }))
  expect(await screen.findByText('Python Fluente')).toBeInTheDocument()
  expect(screen.getByText('Dom Casmurro')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Filtrar por categoria'), {
    target: { value: 'Romance' },
  })

  expect(await screen.findByText('Dom Casmurro')).toBeInTheDocument()
  await waitFor(() =>
    expect(screen.queryByText('Python Fluente')).not.toBeInTheDocument(),
  )

  fireEvent.click(screen.getByLabelText('Layout carrossel'))
  expect(screen.getByLabelText('Carrossel de livros')).toBeInTheDocument()
  expect(screen.getByLabelText('Próximos livros')).toBeInTheDocument()
})

it('deletes a chat session through the accessible row action', async () => {
  let sessions = [
    {
      id: 'session_delete',
      title: 'Conversa para apagar',
      pinned: false,
      pinned_at: null,
      created_at: '2026-06-12T00:00:00Z',
      updated_at: '2026-06-12T01:00:00Z',
    },
  ]

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.includes('/chat/sessions/session_delete') && method === 'DELETE') {
        sessions = []
        return new Response(null, { status: 204 })
      }
      if (url.includes('/chat/sessions') && method === 'GET') {
        return Response.json(sessions)
      }
      return Response.json([])
    }),
  )

  renderApp()

  expect(await screen.findByText('Conversa para apagar')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Excluir conversa' }))

  await waitFor(() =>
    expect(screen.queryByText('Conversa para apagar')).not.toBeInTheDocument(),
  )
})

it('restores pending attachments when sending fails', async () => {
  const createObjectUrl = vi
    .spyOn(URL, 'createObjectURL')
    .mockReturnValue('blob:preview')
  const revokeObjectUrl = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.includes('/chat/sessions') && method === 'POST') {
        return Response.json({
          id: 'session_attachment',
          title: 'Conversa com anexos',
          pinned: false,
          pinned_at: null,
          created_at: '2026-06-11T00:00:00Z',
          updated_at: '2026-06-11T00:00:00Z',
        })
      }
      if (url.includes('/attachments') && method === 'POST') {
        return Response.json({
          id: 'att_1',
          filename: 'diagram.png',
          mime_type: 'image/png',
          size: 3,
          kind: 'image',
          url: '/api/v1/attachments/att_1',
        })
      }
      if (url.includes('/attachments/att_1') && method === 'DELETE') {
        return new Response(null, { status: 204 })
      }
      if (url.includes('/chat/messages') && method === 'POST') {
        return new Response(
          JSON.stringify({ error: { message: 'Falha temporária' } }),
          { status: 500 },
        )
      }
      return Response.json([])
    }),
  )

  const { container } = renderApp()
  const input = container.querySelector('input[type="file"]') as HTMLInputElement
  const file = new File(['png'], 'diagram.png', { type: 'image/png' })

  fireEvent.change(input, { target: { files: [file] } })
  expect(await screen.findByRole('button', { name: 'Remover anexo' })).toBeInTheDocument()

  fireEvent.click(screen.getByLabelText('Enviar mensagem'))

  expect(await screen.findByRole('alert')).toHaveTextContent('Falha temporária')
  expect(screen.getByRole('button', { name: 'Remover anexo' })).toBeInTheDocument()
  expect(createObjectUrl).toHaveBeenCalledWith(file)
  expect(revokeObjectUrl).not.toHaveBeenCalled()
})

it('reuses the same session when a failed send is retried', async () => {
  let createSessionCalls = 0
  let messageAttempts = 0

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.includes('/chat/sessions') && method === 'POST') {
        createSessionCalls += 1
        return Response.json({
          id: 'session_fixed',
          title: 'Conversa',
          pinned: false,
          pinned_at: null,
          created_at: '2026-06-11T00:00:00Z',
          updated_at: '2026-06-11T00:00:00Z',
        })
      }
      if (url.includes('/chat/messages') && method === 'POST') {
        messageAttempts += 1
        if (messageAttempts === 1) {
          return new Response(
            JSON.stringify({ error: { message: 'Falha temporária' } }),
            { status: 500 },
          )
        }
        return Response.json({
          user_message_id: 'msg_user',
          assistant_message_id: 'msg_assistant',
          status: 'completed',
          assistant_message: {
            id: 'msg_assistant',
            session_id: 'session_fixed',
            role: 'assistant',
            content: 'ok',
            thinking_mode: 'balanced',
            status: 'completed',
            trace_id: null,
            attachments: [],
            created_at: '2026-06-11T00:00:00Z',
          },
        })
      }
      return Response.json([])
    }),
  )

  renderApp()

  const composer = await screen.findByPlaceholderText('Pergunte alguma coisa')
  fireEvent.change(composer, { target: { value: 'primeira pergunta' } })
  fireEvent.click(screen.getByLabelText('Enviar mensagem'))

  await waitFor(() => expect(composer).toHaveValue(''))
  await waitFor(() => expect(messageAttempts).toBe(1))
  await waitFor(() => expect(composer).toHaveValue('primeira pergunta'))

  fireEvent.click(screen.getByLabelText('Enviar mensagem'))

  await waitFor(() => expect(messageAttempts).toBe(2))
  expect(createSessionCalls).toBe(1)
})

it('clears the composer immediately and shows thinking while waiting for the model', async () => {
  let resolveMessage: ((value: Response) => void) | undefined

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.includes('/chat/sessions/session_thinking/messages')) {
        return Response.json([
          {
            id: 'msg_user',
            session_id: 'session_thinking',
            role: 'user',
            content: 'Como usar listas?',
            thinking_mode: 'balanced',
            status: 'completed',
            attachments: [],
            created_at: '2026-06-11T00:00:00Z',
          },
          {
            id: 'msg_assistant',
            session_id: 'session_thinking',
            role: 'assistant',
            content: 'Use colchetes.',
            thinking_mode: 'balanced',
            status: 'completed',
            attachments: [],
            created_at: '2026-06-11T00:00:01Z',
          },
        ])
      }
      if (url.includes('/chat/sessions') && method === 'POST') {
        return Response.json({
          id: 'session_thinking',
          title: 'Pergunta',
          pinned: false,
          pinned_at: null,
          created_at: '2026-06-11T00:00:00Z',
          updated_at: '2026-06-11T00:00:00Z',
        })
      }
      if (url.includes('/chat/messages') && method === 'POST') {
        return new Promise<Response>(resolve => {
          resolveMessage = resolve
        })
      }
      return Response.json([])
    }),
  )

  renderApp()

  const composer = await screen.findByPlaceholderText('Pergunte alguma coisa')
  fireEvent.change(composer, { target: { value: 'Como usar listas?' } })
  fireEvent.click(screen.getByLabelText('Enviar mensagem'))

  await waitFor(() => expect(composer).toHaveValue(''))
  expect(screen.getByText('Como usar listas?')).toBeInTheDocument()
  expect(screen.getByLabelText('Assistente pensando')).toBeInTheDocument()
  expect(screen.getByLabelText('Parar geração')).toBeInTheDocument()
  expect(screen.getByLabelText('Anexar arquivo')).toBeDisabled()

  await waitFor(() => expect(resolveMessage).toBeTypeOf('function'))
  resolveMessage!(
    Response.json({
      user_message_id: 'msg_user',
      assistant_message_id: 'msg_assistant',
      status: 'completed',
      assistant_message: {
        id: 'msg_assistant',
        session_id: 'session_thinking',
        role: 'assistant',
        content: 'Use colchetes.',
        thinking_mode: 'balanced',
        status: 'completed',
        attachments: [],
        created_at: '2026-06-11T00:00:01Z',
      },
    }),
  )

  await waitFor(
    () => {
      expect(screen.queryByLabelText('Assistente pensando')).not.toBeInTheDocument()
      expect(screen.getByLabelText('Enviar mensagem')).toBeInTheDocument()
      expect(screen.getByText('Use colchetes.')).toBeInTheDocument()
    },
    { timeout: 10_000 },
  )
})
