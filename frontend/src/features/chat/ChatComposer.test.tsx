import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PendingAttachment } from './attachments'
import { ChatComposer } from './ChatComposer'

const attachments: PendingAttachment[] = [
  {
    id: 'image-1',
    file: new File(['image'], 'diagram.png', { type: 'image/png' }),
    kind: 'image',
    previewUrl: 'blob:diagram',
  },
  {
    id: 'document-1',
    file: new File(['text'], 'notes.txt', { type: 'text/plain' }),
    kind: 'document',
  },
  {
    id: 'audio-1',
    file: new File(['audio'], 'voice.mp3', { type: 'audio/mpeg' }),
    kind: 'audio',
  },
]

function renderComposer(overrides: Partial<Parameters<typeof ChatComposer>[0]> = {}) {
  const props = {
    value: 'pergunta',
    thinkingMode: 'balanced' as const,
    model: 'gpt-test',
    attachments,
    error: 'Falha de teste',
    isSending: false,
    isRecording: false,
    onChange: vi.fn(),
    onSubmit: vi.fn(),
    onStop: vi.fn(),
    onAttachClick: vi.fn(),
    onRemoveAttachment: vi.fn(),
    onToggleRecording: vi.fn(),
    ...overrides,
  }
  return { ...render(<ChatComposer {...props} />), props }
}

describe('ChatComposer', () => {
  it('renders feedback and delegates composer actions', () => {
    const { container, props } = renderComposer()

    expect(screen.getByRole('alert')).toHaveTextContent('Falha de teste')
    expect(container.querySelector('img')).toHaveAttribute('src', 'blob:diagram')

    fireEvent.change(screen.getByPlaceholderText('Pergunte alguma coisa'), {
      target: { value: 'nova pergunta' },
    })
    fireEvent.keyDown(screen.getByPlaceholderText('Pergunte alguma coisa'), {
      key: 'Enter',
    })
    fireEvent.click(screen.getByLabelText('Anexar arquivo'))
    fireEvent.click(screen.getByLabelText('Gravar áudio'))
    fireEvent.click(screen.getAllByLabelText('Remover anexo')[0])
    fireEvent.click(screen.getByLabelText('Enviar mensagem'))

    expect(props.onChange).toHaveBeenCalledWith('nova pergunta')
    expect(props.onSubmit).toHaveBeenCalledTimes(2)
    expect(props.onAttachClick).toHaveBeenCalledOnce()
    expect(props.onToggleRecording).toHaveBeenCalledOnce()
    expect(props.onRemoveAttachment).toHaveBeenCalledWith('image-1')
  })

  it('keeps a shifted newline and exposes stop controls while sending', () => {
    const { props } = renderComposer({
      attachments: [],
      error: null,
      isSending: true,
      isRecording: true,
    })
    const textarea = screen.getByPlaceholderText('Pergunte alguma coisa')

    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    fireEvent.click(screen.getByLabelText('Parar geração'))

    expect(props.onSubmit).not.toHaveBeenCalled()
    expect(props.onStop).toHaveBeenCalledOnce()
    expect(screen.getByLabelText('Anexar arquivo')).toBeDisabled()
    expect(screen.getByLabelText('Parar gravação')).toBeDisabled()
  })
})
