import { useState, useEffect, useCallback, useRef } from 'react'
import { ModalHost } from './ModalHost'
import { useI18n, type TranslationKey } from '../i18n'
import { desktopAuthErrorKey } from '../desktop_messages_locale'

type Props = {
  onClose: () => void
  onAuthenticated: (method: 'api_key' | 'subscription') => void
  isAuthenticated: boolean
  authMethod: string | null
}

export function ClaudeLogin({ onClose, onAuthenticated, isAuthenticated, authMethod }: Props) {
  const { t } = useI18n()
  const [tab, setTab] = useState<'api_key' | 'subscription'>('api_key')
  const [apiKey, setApiKey] = useState('')
  const [validating, setValidating] = useState(false)
  const [error, setError] = useState<TranslationKey | ''>('')
  const [success, setSuccess] = useState<TranslationKey | ''>('')
  const requestPending = useRef(false)

  // Load existing key (masked) on mount.
  useEffect(() => {
    let active = true
    window.api.getClaudeAuth().then(auth => {
      if (!active) return
      if (auth.method === 'api_key' && auth.keyHint) {
        setApiKey(auth.keyHint)
      }
    }).catch(() => { if (active) setError('desktopAuthLoadFailed') })
    return () => { active = false }
  }, [])

  const handleSaveApiKey = useCallback(async () => {
    if (requestPending.current) return
    const key = apiKey.trim()
    if (!key) {
      setError('apiKeyRequired')
      return
    }
    if (!key.startsWith('sk-ant-')) {
      setError('apiKeyInvalid')
      return
    }

    requestPending.current = true
    setValidating(true)
    setError('')
    setSuccess('')

    try {
      const result = await window.api.saveClaudeKey(key)
      if (result.success) {
        setSuccess('apiKeySaved')
        setApiKey(result.keyHint || key.slice(0, 10) + '...')
        onAuthenticated('api_key')
      } else setError(desktopAuthErrorKey(result.error, 'desktopAuthSaveFailed'))
    } catch { setError('desktopAuthSaveFailed') }
    finally { requestPending.current = false; setValidating(false) }
  }, [apiKey, onAuthenticated])

  const handleLogout = useCallback(async () => {
    if (requestPending.current) return
    requestPending.current = true
    setValidating(true)
    try {
      const result = await window.api.deleteClaudeAuth()
      if (!result.success) { setError('desktopAuthLogoutFailed'); return }
      setApiKey(''); setSuccess(''); setError('')
      // Notify parent only after the host reports removal.
      window.api.sendToPython({ id: Date.now(), type: 'claude_logout' })
    } catch { setError('desktopAuthLogoutFailed') }
    finally { requestPending.current = false; setValidating(false) }
  }, [])

  const handleSubscriptionLogin = useCallback(async () => {
    if (requestPending.current) return
    requestPending.current = true
    setValidating(true)
    setError('')
    setSuccess('')

    try {
      const result = await window.api.startClaudeOAuth()
      if (result.success) { setSuccess('loggedIn'); onAuthenticated('subscription') }
      else setError(desktopAuthErrorKey(result.error))
    } catch { setError('desktopAuthFailed') }
    finally { requestPending.current = false; setValidating(false) }
  }, [onAuthenticated])

  return (
    <ModalHost onClose={onClose} label={t('claudeAuthentication')} className="claude-login">
        <div className="claude-login-header">
          <span className="claude-login-title">{t('claudeAuthentication')}</span>
          <button className="settings-close" onClick={onClose} aria-label={t('closeDialog')}>×</button>
        </div>

        {isAuthenticated && (
          <div className="claude-login-status">
            <span className="claude-login-status-dot" />
            <span>{t('authenticatedVia')} {authMethod === 'api_key' ? t('apiKey') : t('subscription')}</span>
            <button className="claude-logout-btn" onClick={handleLogout} disabled={validating}>{t('logout')}</button>
          </div>
        )}

        <div className="claude-login-tabs">
          <button
            className={`claude-login-tab ${tab === 'api_key' ? 'active' : ''}`}
            onClick={() => { setTab('api_key'); setError(''); setSuccess('') }}
          >
            {t('apiKey')}
          </button>
          <button
            className={`claude-login-tab ${tab === 'subscription' ? 'active' : ''}`}
            onClick={() => { setTab('subscription'); setError(''); setSuccess('') }}
          >
            {t('subscription')}
          </button>
        </div>

        <div className="claude-login-body">
          {tab === 'api_key' ? (
            <div className="claude-login-section">
              <div className="claude-login-desc">
                {t('enterApiKey')}{' '}
                <button type="button"
                  className="claude-login-link"
                  onClick={() => { window.api.openExternalUrl('https://console.anthropic.com/settings/keys').catch(() => setError('desktopAuthExternalFailed')) }}
                >
                  console.anthropic.com
                </button>
              </div>
              <div className="claude-login-field">
                <input
                  type="password"
                  aria-label={t('apiKey')}
                  autoComplete="off"
                  className="claude-login-input"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder="sk-ant-api03-..."
                  onKeyDown={e => { if (e.key === 'Enter') handleSaveApiKey() }}
                  autoFocus
                />
              </div>
              <button
                className="claude-login-btn primary"
                onClick={handleSaveApiKey}
                disabled={validating || !apiKey.trim()}
              >
                {validating ? t('validating') : t('saveValidate')}
              </button>
            </div>
          ) : (
            <div className="claude-login-section">
              <div className="claude-login-desc">
                {t('subscriptionDescription')}
              </div>
              <button
                className="claude-login-btn primary"
                onClick={handleSubscriptionLogin}
                disabled={validating}
              >
                {validating ? t('loggingIn') : t('loginClaude')}
              </button>
              <div className="claude-login-hint">
                {t('subscriptionRequired')}
              </div>
            </div>
          )}

          {error && <div className="claude-login-error" role="alert">{t(error)}</div>}
          {success && <div className="claude-login-success" role="status">{t(success)}</div>}
        </div>
    </ModalHost>
  )
}
