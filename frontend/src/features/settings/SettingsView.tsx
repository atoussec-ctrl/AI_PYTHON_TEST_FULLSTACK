import { useState } from 'react'
import { KeyRound, Moon, Sun } from 'lucide-react'

import type { AppTheme } from '@/app/types'
import { Button } from '@/components/ui/button'
import {
  MODEL_OPTIONS,
  THINKING_OPTIONS,
  type ChatModel,
} from '@/features/chat/config'
import type { ThinkingMode } from '@/shared/api/types'
import { readApiCredential, saveApiCredential } from '@/shared/api/credentials'

interface SettingsViewProps {
  theme: AppTheme
  model: ChatModel
  thinkingMode: ThinkingMode
  onThemeToggle: () => void
  onModelChange: (model: ChatModel) => void
  onThinkingChange: (mode: ThinkingMode) => void
}

export function SettingsView({
  theme,
  model,
  thinkingMode,
  onThemeToggle,
  onModelChange,
  onThinkingChange,
}: SettingsViewProps) {
  const [apiCredential, setApiCredential] = useState(readApiCredential)

  return (
    <section className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-8">
      <div className="mx-auto w-full max-w-2xl space-y-4">
        <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="text-base font-semibold">Aparência</h2>
          <div className="mt-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium">Tema</p>
              <p className="text-xs text-muted-foreground">
                Alterna entre claro e escuro. A preferência fica salva neste navegador.
              </p>
            </div>
            <Button
              variant="soft"
              aria-label="Alternar tema nas configurações"
              onClick={onThemeToggle}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              {theme === 'dark' ? 'Claro' : 'Escuro'}
            </Button>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="text-base font-semibold">Assistente</h2>
          <label className="mt-4 block">
            <span className="mb-1 block text-sm font-medium">Modelo padrão</span>
            <select
              aria-label="Modelo padrão"
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={model}
              onChange={event => onModelChange(event.target.value as ChatModel)}
            >
              {MODEL_OPTIONS.map(option => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-4 block">
            <span className="mb-1 block text-sm font-medium">Modo de raciocínio</span>
            <select
              aria-label="Modo de raciocínio padrão"
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={thinkingMode}
              onChange={event => onThinkingChange(event.target.value as ThinkingMode)}
            >
              {THINKING_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label} — {option.detail}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <KeyRound size={16} />
            Acesso à API
          </h2>
          <label className="mt-4 block">
            <span className="mb-1 block text-sm font-medium">Credencial da API</span>
            <input
              aria-label="Credencial da API"
              type="password"
              autoComplete="current-password"
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={apiCredential}
              onChange={event => {
                const value = event.target.value
                setApiCredential(value)
                saveApiCredential(value)
              }}
              placeholder="Obrigatória quando API_KEY está configurada"
            />
          </label>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Guardada somente nesta sessão do navegador. Nunca incorpore segredos em
            variáveis `VITE_*`; para deploy público, prefira um proxy ou BFF.
          </p>
        </div>

        <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="text-base font-semibold">Sobre</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Aplicação</dt>
              <dd className="font-medium">
                {import.meta.env.VITE_APP_NAME ?? 'MindSight AI'}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">API</dt>
              <dd className="truncate font-mono text-xs">
                {import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5000/api/v1'}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  )
}
