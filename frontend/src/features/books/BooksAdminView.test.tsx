import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BooksAdminView } from './BooksAdminView'

const book = {
  id: 'book-1',
  title: 'Clean Architecture',
  category: 'Arquitetura',
  author: 'Robert Martin',
  publication_date: '2017-01-01',
  publication_year: 2017,
  summary: 'Princípios de arquitetura.',
}

function renderView(onAskBook = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <BooksAdminView
          actionError={null}
          isAskingBook={false}
          onAskBook={onAskBook}
        />
      </QueryClientProvider>,
    ),
    onAskBook,
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('BooksAdminView', () => {
  it('creates a book, imports metadata and delegates the AI action', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.includes('/books/import') && method === 'POST') {
        return Response.json({ book, extracted: book })
      }
      if (url.endsWith('/books') && method === 'POST') {
        return Response.json(book)
      }
      return Response.json([book])
    })
    vi.stubGlobal('fetch', fetchMock)
    const { onAskBook } = renderView()

    expect(await screen.findByText('Clean Architecture')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Título'), {
      target: { value: 'Novo livro' },
    })
    fireEvent.change(screen.getByLabelText('Autor'), { target: { value: 'Autora' } })
    fireEvent.change(screen.getByLabelText('Ano de publicação'), {
      target: { value: '2024' },
    })
    fireEvent.change(screen.getByLabelText('Resumo'), { target: { value: 'Resumo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cadastrar livro' }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/books'),
        expect.objectContaining({ method: 'POST' }),
      ),
    )
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) => url.endsWith('/books') && init?.method === 'POST',
    )
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      title: 'Novo livro',
      publication_year: 2024,
    })
    await waitFor(() => expect(screen.getByLabelText('Título')).toHaveValue(''))

    const file = new File(['metadata'], 'book.json', { type: 'application/json' })
    fireEvent.change(screen.getByLabelText('Upload de livro'), {
      target: { files: [file] },
    })
    expect(await screen.findByText('Livro importado: Clean Architecture')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Perguntar à IA' }))
    expect(onAskBook).toHaveBeenCalledWith(book)
  })

  it('clears filters and scrolls both carousel directions', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json([book])))
    renderView()

    expect(await screen.findByText('Clean Architecture')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Buscar livros'), {
      target: { value: 'clean' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Limpar filtros' }))
    expect(screen.getByLabelText('Buscar livros')).toHaveValue('')

    fireEvent.click(screen.getByLabelText('Layout carrossel'))
    const carousel = screen.getByLabelText('Carrossel de livros')
    const scrollBy = vi.fn()
    Object.defineProperty(carousel, 'clientWidth', { configurable: true, value: 300 })
    Object.defineProperty(carousel, 'scrollBy', { configurable: true, value: scrollBy })

    fireEvent.click(screen.getByLabelText('Próximos livros'))
    fireEvent.click(screen.getByLabelText('Livros anteriores'))

    expect(scrollBy).toHaveBeenNthCalledWith(1, {
      left: 270,
      behavior: 'smooth',
    })
    expect(scrollBy).toHaveBeenNthCalledWith(2, {
      left: -270,
      behavior: 'smooth',
    })
  })
})
