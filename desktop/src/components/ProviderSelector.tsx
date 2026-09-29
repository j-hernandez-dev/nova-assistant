import { useState, useRef, useEffect, useCallback } from 'react'

type Props = {
  currentProvider: string
  hasClaude: boolean
  disabled: boolean
  onSwitch: (provider: string) => void
  onLoginRequest?: () => void
}

type ProviderOption = {
  id: string
  label: string
  description: string
}

const PROVIDERS: ProviderOption[] = [
  { id: 'claude', label: 'Claude Code', description: 'Anthropic API' },
  { id: 'ollama', label: 'Local LLM', description: 'Ollama' },
]

export function ProviderSelector({ currentProvider, hasClaude, disabled, onSwitch, onLoginRequest }: Props) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close on Escape key.
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open])

  // Close on click outside.
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    window.addEventListener('mousedown', handler)
    return () => window.removeEventListener('mousedown', handler)
  }, [open])

  const handleSelect = useCallback((providerId: string) => {
    if (disabled) return
    if (providerId === currentProvider) {
      setOpen(false)
      return
    }

    if (providerId === 'claude' && !hasClaude) {
      setOpen(false)
      onLoginRequest?.()
      return
    }

    onSwitch(providerId)
    setOpen(false)
  }, [currentProvider, hasClaude, disabled, onSwitch])

  const displayLabel = PROVIDERS.find(p => p.id === currentProvider)?.description || currentProvider

  return (
    <div className="provider-select-container" ref={containerRef}>
      <span
        className="model-select"
        onClick={() => { if (!disabled) setOpen(!open) }}
        aria-disabled={disabled}
        title="Click to switch provider"
      >
        {displayLabel}
      </span>

      {open && (
        <div className="provider-dropdown">
          {
            PROVIDERS.map(p => {
              const isActive = p.id === currentProvider
              const needsLogin = p.id === 'claude' && !hasClaude

              return (
                <div
                  key={p.id}
                  className={`provider-option ${isActive ? 'active' : ''}`}
                  onClick={() => handleSelect(p.id)}
                >
                  <span className="provider-check">{isActive ? '✓' : ''}</span>
                  <div className="provider-option-info">
                    <span className="provider-option-label">{p.label}</span>
                    <span className="provider-option-desc">
                      {needsLogin ? 'Login required' : p.description}
                    </span>
                  </div>
                  {needsLogin && (
                    <span className="provider-login-badge">Login</span>
                  )}
                </div>
              )
            })
          }
        </div>
      )}
    </div>
  )
}
