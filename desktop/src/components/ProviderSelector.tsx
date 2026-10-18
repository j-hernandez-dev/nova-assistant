import { useState, useRef, useEffect, useCallback, useId } from 'react'
import { useI18n } from '../i18n'

type Props = {
  currentProvider: string
  hasClaude: boolean
  disabled: boolean
  onSwitch: (provider: string) => void
  onLoginRequest?: () => void
}

const PROVIDERS = ['claude', 'ollama'] as const

export function ProviderSelector({ currentProvider, hasClaude, disabled, onSwitch, onLoginRequest }: Props) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [focused, setFocused] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([])
  const menuId = useId()

  useEffect(() => {
    if (disabled) setOpen(false)
  }, [disabled])

  useEffect(() => {
    if (!open) return
    optionRefs.current[focused]?.focus()
  }, [open, focused])

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', handler)
    return () => window.removeEventListener('mousedown', handler)
  }, [open])

  const handleSelect = useCallback((providerId: string) => {
    if (disabled) return
    setOpen(false)
    triggerRef.current?.focus()
    if (providerId === currentProvider) return
    if (providerId === 'claude' && !hasClaude) { onLoginRequest?.(); return }
    onSwitch(providerId)
  }, [currentProvider, hasClaude, disabled, onSwitch, onLoginRequest])

  function showMenu() {
    if (disabled) return
    setFocused(Math.max(0, PROVIDERS.findIndex(p => p === currentProvider)))
    setOpen(value => !value)
  }

  const displayLabel = currentProvider === 'ollama' ? 'Ollama'
    : currentProvider === 'claude' ? t('desktopProviderAnthropic') : currentProvider

  return (
    <div className="provider-select-container" ref={containerRef}>
      <button type="button" className="model-select" ref={triggerRef} onClick={showMenu}
        disabled={disabled} title={t('desktopProviderSwitch')} aria-label={t('desktopProvider') + ': ' + displayLabel}
        aria-haspopup="menu" aria-expanded={open} aria-controls={open ? menuId : undefined}
        onKeyDown={event => {
          if (!disabled && ['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); showMenu() }
        }}>
        {displayLabel}
      </button>

      {open && <div className="provider-dropdown" role="menu" id={menuId} aria-label={t('desktopProvider')}
        onKeyDown={event => {
          if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setOpen(false); triggerRef.current?.focus() }
          else if (event.key === 'Tab') setOpen(false)
          else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault(); setFocused(value => (value + (event.key === 'ArrowDown' ? 1 : PROVIDERS.length - 1)) % PROVIDERS.length)
          } else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); setFocused(event.key === 'Home' ? 0 : PROVIDERS.length - 1) }
        }}>
        {PROVIDERS.map((provider, index) => {
          const active = provider === currentProvider
          const needsLogin = provider === 'claude' && !hasClaude
          return <button type="button" key={provider} role="menuitemradio" aria-checked={active}
            className={`provider-option ${active ? 'active' : ''}`} onClick={() => handleSelect(provider)}
            ref={element => { optionRefs.current[index] = element }} tabIndex={focused === index ? 0 : -1}>
            <span className="provider-check" aria-hidden="true">{active ? '✓' : ''}</span>
            <span className="provider-option-info">
              <span className="provider-option-label">{provider === 'claude' ? 'Claude Code' : t('desktopProviderLocal')}</span>
              <span className="provider-option-desc">{needsLogin ? t('desktopProviderLoginRequired') : provider === 'claude' ? t('desktopProviderAnthropic') : 'Ollama'}</span>
            </span>
            {needsLogin && <span className="provider-login-badge">{t('desktopProviderLogin')}</span>}
          </button>
        })}
      </div>}
    </div>
  )
}
