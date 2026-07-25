import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ChatHeader } from './ChatHeader'

describe('ChatHeader', () => {
  it('delegates navigation and assistant controls', () => {
    const onToggleSidebar = vi.fn()
    const onModelChange = vi.fn()
    const onThinkingChange = vi.fn()
    const onThemeToggle = vi.fn()

    render(
      <ChatHeader
        title="Conversa"
        model="deepseek-ai/DeepSeek-V4-Flash"
        thinkingMode="balanced"
        theme="light"
        isMobileSidebarOpen={false}
        onToggleSidebar={onToggleSidebar}
        onModelChange={onModelChange}
        onThinkingChange={onThinkingChange}
        onThemeToggle={onThemeToggle}
      />,
    )

    fireEvent.click(screen.getByLabelText('Abrir menu'))
    fireEvent.change(screen.getByLabelText('Modelo'), {
      target: { value: 'gpt-4.1-mini' },
    })
    fireEvent.change(screen.getByLabelText('Thinking'), { target: { value: 'deep' } })
    fireEvent.click(screen.getByLabelText('Alternar tema'))

    expect(onToggleSidebar).toHaveBeenCalledOnce()
    expect(onModelChange).toHaveBeenCalledWith('gpt-4.1-mini')
    expect(onThinkingChange).toHaveBeenCalledWith('deep')
    expect(onThemeToggle).toHaveBeenCalledOnce()
  })
})
