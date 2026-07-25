import { useMemo, useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  GalleryHorizontal,
  LayoutGrid,
  Search,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { createBook, importBook, listBooks } from '@/shared/api/client'
import type { Book, CreateBookInput } from '@/shared/api/types'
import { BookCard } from './BookCard'

type BooksLayout = 'grid' | 'carousel'

interface BooksAdminViewProps {
  actionError: string | null
  isAskingBook: boolean
  onAskBook: (book: Book) => void
}

interface BookFormState {
  title: string
  category: string
  author: string
  publication_year: string
  summary: string
}

const EMPTY_BOOK_FORM: BookFormState = {
  title: '',
  category: 'Programação',
  author: '',
  publication_year: '',
  summary: '',
}

export function BooksAdminView({
  actionError,
  isAskingBook,
  onAskBook,
}: BooksAdminViewProps) {
  const queryClient = useQueryClient()
  const importInputRef = useRef<HTMLInputElement | null>(null)
  const carouselRef = useRef<HTMLDivElement | null>(null)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [authorFilter, setAuthorFilter] = useState('')
  const [layout, setLayout] = useState<BooksLayout>('grid')
  const [form, setForm] = useState<BookFormState>(EMPTY_BOOK_FORM)
  const [importedBookTitle, setImportedBookTitle] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const booksQuery = useQuery({
    queryKey: ['books', search, categoryFilter, authorFilter],
    queryFn: () =>
      listBooks({ q: search, category: categoryFilter, author: authorFilter }),
  })

  // Catálogo completo apenas para montar as opções dos filtros.
  const allBooksQuery = useQuery({
    queryKey: ['books', 'all'],
    queryFn: () => listBooks(),
  })
  const filterOptions = useMemo(() => {
    const catalog = allBooksQuery.data ?? []
    return {
      categories: [...new Set(catalog.map(book => book.category))].sort(),
      authors: [...new Set(catalog.map(book => book.author))].sort(),
    }
  }, [allBooksQuery.data])

  function scrollCarousel(direction: 1 | -1) {
    const node = carouselRef.current
    if (!node) return
    node.scrollBy({ left: direction * node.clientWidth * 0.9, behavior: 'smooth' })
  }

  const createBookMutation = useMutation({
    mutationFn: createBook,
    onSuccess: () => {
      setForm(EMPTY_BOOK_FORM)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['books'] })
    },
    onError: mutationError => {
      setError(
        mutationError instanceof Error
          ? mutationError.message
          : 'Falha ao cadastrar livro.',
      )
    },
  })

  const importBookMutation = useMutation({
    mutationFn: importBook,
    onSuccess: response => {
      setImportedBookTitle(response.book.title)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['books'] })
      if (importInputRef.current) {
        importInputRef.current.value = ''
      }
    },
    onError: mutationError => {
      setImportedBookTitle(null)
      setError(
        mutationError instanceof Error
          ? mutationError.message
          : 'Falha ao importar livro.',
      )
    },
  })

  function updateForm(field: keyof BookFormState, value: string) {
    setForm(current => ({ ...current, [field]: value }))
  }

  function submitBook(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const input: CreateBookInput = {
      ...form,
      publication_year: Number(form.publication_year),
    }
    createBookMutation.mutate(input)
  }

  const books = booksQuery.data ?? []

  return (
    <section className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-8">
      <div className="mx-auto grid w-full max-w-6xl gap-6 xl:grid-cols-[380px_1fr]">
        <form
          className="h-fit rounded-lg border border-border bg-card p-4 shadow-sm"
          onSubmit={submitBook}
        >
          <div className="mb-4">
            <h2 className="text-base font-semibold">Administração</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Cadastre livros manualmente ou importe um arquivo com metadados.
            </p>
          </div>

          {actionError && (
            <div
              className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              role="alert"
            >
              {actionError}
            </div>
          )}

          <div className="mb-5 rounded-md border border-border bg-secondary/45 p-3">
            <p className="text-sm font-medium">Importar livro com IA</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Envie `.txt`, `.md`, `.json` ou `.pdf` contendo título, autor, categoria,
              ano e resumo. O backend extrai e cadastra o livro automaticamente.
            </p>
            <div className="mt-3 flex gap-2">
              <input
                ref={importInputRef}
                aria-label="Upload de livro"
                className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
                type="file"
                accept=".txt,.md,.json,.pdf"
                onChange={event => {
                  const file = event.target.files?.[0]
                  if (file) importBookMutation.mutate(file)
                }}
              />
            </div>
            {importBookMutation.isPending && (
              <p className="mt-2 text-xs text-muted-foreground">Extraindo metadados...</p>
            )}
            {importedBookTitle && (
              <p className="mt-2 text-xs text-emerald-600">
                Livro importado: {importedBookTitle}
              </p>
            )}
          </div>

          <label className="mb-3 block">
            <span className="mb-1 block text-sm font-medium">Título</span>
            <input
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.title}
              onChange={event => updateForm('title', event.target.value)}
              placeholder="Python Fluente"
              required
            />
          </label>

          <label className="mb-3 block">
            <span className="mb-1 block text-sm font-medium">Categoria</span>
            <input
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.category}
              onChange={event => updateForm('category', event.target.value)}
              placeholder="Programação"
            />
          </label>

          <label className="mb-3 block">
            <span className="mb-1 block text-sm font-medium">Autor</span>
            <input
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.author}
              onChange={event => updateForm('author', event.target.value)}
              placeholder="Luciano Ramalho"
              required
            />
          </label>

          <label className="mb-3 block">
            <span className="mb-1 block text-sm font-medium">Ano de publicação</span>
            <input
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.publication_year}
              onChange={event => updateForm('publication_year', event.target.value)}
              type="number"
              inputMode="numeric"
              min={1000}
              max={9999}
              placeholder="2015"
              required
            />
          </label>

          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium">Resumo</span>
            <Textarea
              className="min-h-28 rounded-md border border-border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-ring"
              value={form.summary}
              onChange={event => updateForm('summary', event.target.value)}
              placeholder="Descreva o conteúdo do livro para a IA usar como fonte."
              required
            />
          </label>

          {error && (
            <div
              className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              role="alert"
            >
              {error}
            </div>
          )}

          <Button className="w-full" disabled={createBookMutation.isPending}>
            {createBookMutation.isPending ? 'Salvando...' : 'Cadastrar livro'}
          </Button>
        </form>

        <div className="min-w-0">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">Consulta de livros</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Busque por título, autor ou termos do resumo. A IA usa esses registros
                como contexto local.
              </p>
            </div>
            <label className="relative block sm:w-[320px]">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                size={17}
              />
              <input
                aria-label="Buscar livros"
                className="h-10 w-full rounded-md border border-border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder="Buscar livros"
              />
            </label>
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            <select
              aria-label="Filtrar por categoria"
              className="h-9 rounded-md border border-border bg-background px-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={categoryFilter}
              onChange={event => setCategoryFilter(event.target.value)}
            >
              <option value="">Todas as categorias</option>
              {filterOptions.categories.map(category => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
            <select
              aria-label="Filtrar por autor"
              className="h-9 rounded-md border border-border bg-background px-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={authorFilter}
              onChange={event => setAuthorFilter(event.target.value)}
            >
              <option value="">Todos os autores</option>
              {filterOptions.authors.map(author => (
                <option key={author} value={author}>
                  {author}
                </option>
              ))}
            </select>
            {(categoryFilter || authorFilter || search) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch('')
                  setCategoryFilter('')
                  setAuthorFilter('')
                }}
              >
                <X size={14} />
                Limpar filtros
              </Button>
            )}
            <div className="ml-auto flex items-center gap-1 rounded-md border border-border p-0.5">
              <Button
                variant={layout === 'grid' ? 'soft' : 'ghost'}
                size="icon"
                aria-label="Layout em grade"
                onClick={() => setLayout('grid')}
              >
                <LayoutGrid size={16} />
              </Button>
              <Button
                variant={layout === 'carousel' ? 'soft' : 'ghost'}
                size="icon"
                aria-label="Layout carrossel"
                onClick={() => setLayout('carousel')}
              >
                <GalleryHorizontal size={16} />
              </Button>
            </div>
          </div>

          {booksQuery.isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="h-56 rounded-lg bg-secondary animate-shimmer" />
              <div className="h-56 rounded-lg bg-secondary animate-shimmer" />
            </div>
          ) : books.length > 0 ? (
            layout === 'grid' ? (
              <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                {books.map(book => (
                  <BookCard
                    key={book.id}
                    book={book}
                    isAskingBook={isAskingBook}
                    onAskBook={() => onAskBook(book)}
                  />
                ))}
              </div>
            ) : (
              <div className="relative">
                <div
                  ref={carouselRef}
                  aria-label="Carrossel de livros"
                  className="flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth pb-3"
                >
                  {books.map(book => (
                    <div key={book.id} className="w-[290px] shrink-0 snap-start sm:w-[320px]">
                      <BookCard
                        book={book}
                        isAskingBook={isAskingBook}
                        onAskBook={() => onAskBook(book)}
                      />
                    </div>
                  ))}
                </div>
                <div className="mt-1 flex justify-end gap-2">
                  <Button
                    variant="soft"
                    size="icon"
                    aria-label="Livros anteriores"
                    onClick={() => scrollCarousel(-1)}
                  >
                    <ChevronLeft size={17} />
                  </Button>
                  <Button
                    variant="soft"
                    size="icon"
                    aria-label="Próximos livros"
                    onClick={() => scrollCarousel(1)}
                  >
                    <ChevronRight size={17} />
                  </Button>
                </div>
              </div>
            )
          ) : (
            <div className="rounded-lg border border-dashed border-border p-8 text-center">
              <BookOpen className="mx-auto mb-3 text-muted-foreground" size={28} />
              <p className="font-medium">Nenhum livro encontrado</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Cadastre um livro ou ajuste a busca.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
