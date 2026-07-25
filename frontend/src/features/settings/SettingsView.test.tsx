import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SettingsView } from './SettingsView'

describe('SettingsView', () => {
  it('delegates theme, model and thinking preferences', () => {
    sessionStorage.clear()
    const onThemeToggle = vi.fn()
    const onModelChange = vi.fn()
    const onThinkingChange = vi.fn()

    render(
      <SettingsView
        theme="dark"
        model="deepseek-ai/DeepSeek-V4-Flash"
        thinkingMode="balanced"
        onThemeToggle={onThemeToggle}
        onModelChange={onModelChange}
        onThinkingChange={onThinkingChange}
      />,
    )

    fireEvent.click(screen.getByLabelText('Alternar tema nas configurações'))
    fireEvent.change(screen.getByLabelText('Modelo padrão'), {
      target: { value: 'gpt-4.1-mini' },
    })
    fireEvent.change(screen.getByLabelText('Modo de raciocínio padrão'), {
      target: { value: 'deep' },
    })
    fireEvent.change(screen.getByLabelText('Credencial da API'), {
      target: { value: 'runtime-secret' },
    })

    expect(onThemeToggle).toHaveBeenCalledOnce()
    expect(onModelChange).toHaveBeenCalledWith('gpt-4.1-mini')
    expect(onThinkingChange).toHaveBeenCalledWith('deep')
    expect(screen.getByText('Claro')).toBeInTheDocument()
    expect(sessionStorage.getItem('mindsight-api-key')).toBe('runtime-secret')
  })
})
