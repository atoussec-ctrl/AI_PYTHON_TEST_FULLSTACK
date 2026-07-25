import { Calendar, Sparkles, UserRound } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { Book } from '@/shared/api/types'

interface BookCardProps {
  book: Book
  isAskingBook: boolean
  onAskBook: () => void
}

export function BookCard({ book, isAskingBook, onAskBook }: BookCardProps) {
  return (
    <article className="flex h-full flex-col rounded-lg border border-border bg-card p-4 shadow-sm transition hover:shadow-md">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge>{book.category}</Badge>
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Calendar size={13} />
          {book.publication_year}
        </span>
      </div>
      <h3 className="text-base font-semibold leading-snug">{book.title}</h3>
      <p className="mt-1 inline-flex items-center gap-1 text-sm text-muted-foreground">
        <UserRound size={14} />
        {book.author}
      </p>
      <p className="mt-2 line-clamp-4 flex-1 text-sm leading-6 text-muted-foreground">
        {book.summary}
      </p>
      <Button
        className="mt-4 w-full"
        disabled={isAskingBook}
        variant="soft"
        onClick={onAskBook}
      >
        <Sparkles size={16} />
        Perguntar à IA
      </Button>
    </article>
  )
}
