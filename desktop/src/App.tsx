import { useState, useEffect, useRef, useCallback } from 'react'
import type { PythonMessage } from './types'
import { useSessionView } from './use_session_view'
import { Banner } from './components/Banner'
import { MessageBlock } from './components/MessageBlock'
import { ModelPicker, CatalogModel, SearchResult, Recommendation, SystemInfo } from './components/ModelPicker'
import { FileExplorer } from './components/FileExplorer'
import { ProviderSelector } from './components/ProviderSelector'
import { FileViewer } from './components/FileViewer'
import { SettingsPanel } from './components/SettingsPanel'
import { ClaudeLogin } from './components/ClaudeLogin'

let reqIdCounter = 0
function nextId() { return ++reqIdCounter }

type Catalog = { categories: string[]; models: CatalogModel[] }

export default function App() {
  const view = useSessionView()
  const messages = view?.messages || []
  const status = view?.status || { model: '', provider: '', connected: false, tools: [], ready: false }
  const streaming = !!view?.activeTurnId
  const confirmReq = view?.approvals[0] || null
  const askReq = view?.inputs[0] || null
  const [resumeDismissed, setResumeDismissed] = useState(false)
  const resumable = resumeDismissed ? null : view?.resumable
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [showPicker, setShowPicker] = useState(false)
  const [pulling, setPulling] = useState<string | null>(null)
  const [pullProgress, setPullProgress] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [recommendations, setRecommendations] = useState<Recommendation[] | null>(null)
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null)
  const [updating, setUpdating] = useState(false)
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const [updateMessage, setUpdateMessage] = useState('')
  const [appUpdating, setAppUpdating] = useState(false)
  const [appUpdateResult, setAppUpdateResult] = useState('')
  const [autoUpdateProgress, setAutoUpdateProgress] = useState<{ stage: string; percent: number; version?: string } | null>(null)
  const [explorerOpen, setExplorerOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showClaudeLogin, setShowClaudeLogin] = useState(false)
  const [claudeAuthMethod, setClaudeAuthMethod] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [hasClaude, setHasClaude] = useState(false)
  const [rootDir, setRootDir] = useState<string | null>(null)
  const [appVersion, setAppVersion] = useState('')
  const [backendGitCapability, setBackendGitCapability] = useState<'UNAVAILABLE' | 'AVAILABLE_NOT_REPOSITORY' | 'AVAILABLE_REPOSITORY' | null>(null)
  const [askAnswer, setAskAnswer] = useState('')
  const explorerRefreshKey = view?.fileRevision || 0
  const terminalRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [inputText, setInputText] = useState('')

  const scrollToBottom = useCallback(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  useEffect(() => { setAskAnswer('') }, [askReq?.inputRequestId])
  useEffect(() => {
    if (view?.workspace) setRootDir(view.workspace)
    setResumeDismissed(false)
  }, [view?.workspace])

  // Initialize host metadata on mount.
  useEffect(() => {
    if (!window.api) return
    window.api.getAppVersion().then(setAppVersion)
    window.api.hasClaudeAccess().then(setHasClaude)
    // Don't auto-set rootDir — let the user choose via Open Folder.
    window.api.getClaudeAuth().then(auth => {
      if (auth.authenticated) {
        setHasClaude(true)
        setClaudeAuthMethod(auth.method)
      }
    })
  }, [])

  // Listen for auto-update events from main process.
  useEffect(() => {
    if (!window.api) return
    const cleanupStart = window.api.onAutoUpdateStart((info) => {
      setAutoUpdateProgress({ stage: 'starting', percent: 0, version: info.version })
    })
    const cleanupProgress = window.api.onUpdateProgress((progress) => {
      setAutoUpdateProgress(progress)
    })
    return () => { cleanupStart(); cleanupProgress() }
  }, [])

  // Cmd/Ctrl+, keyboard shortcut for settings.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === ',') {
        e.preventDefault()
        setShowSettings(prev => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Cmd/Ctrl+B keyboard shortcut to toggle file explorer.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault()
        setExplorerOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleTerminalClick = useCallback(() => {
    // Don't steal focus if the user is selecting text for copy.
    const sel = window.getSelection()
    if (sel && sel.toString().length > 0) return
    inputRef.current?.focus()
  }, [])

  const refreshCatalog = useCallback(() => {
    window.api.sendToPython({ id: nextId(), type: 'catalog' })
  }, [])

  // Listen to Python messages.
  useEffect(() => {
    if (!window.api) return

    const cleanup = window.api.onPythonMessage((msg: PythonMessage) => {
      switch (msg.type) {
        case 'ready':
          setBackendGitCapability(msg.backend_git_capability || null)
          // Read has_claude from ready message.
          if (msg.has_claude !== undefined) {
            setHasClaude(!!msg.has_claude)
          }
          // Offer to restore this folder's previous conversation.
          // Fetch catalog.
          window.api.sendToPython({ id: nextId(), type: 'catalog' })
          break

        case 'catalog':
          if (msg.data && typeof msg.data === 'object') {
            setCatalog(msg.data as Catalog)
          }
          break

        case 'search_results':
          if (Array.isArray(msg.data)) {
            setSearchResults(msg.data as SearchResult[])
          }
          setSearching(false)
          break

        case 'recommend':
          if (msg.models) setRecommendations(msg.models as Recommendation[])
          if (msg.system) setSystemInfo(msg.system as SystemInfo)
          break

        case 'catalog_updating':
          setUpdating(true)
          break

        case 'catalog_updated':
          setUpdating(false)
          // Refresh catalog with new data.
          window.api.sendToPython({ id: nextId(), type: 'catalog' })
          break

        case 'pull_start': {
          // Server-initiated pull (e.g. auto-pull on model switch).
          const pullModel = (msg as any).model || ''
          if (pullModel) {
            setPulling(pullModel)
            setPullProgress('starting...')
          }
          break
        }

        case 'pull_progress': {
          const completed = (msg as any).completed
          const total = (msg as any).total
          const pStatus = (msg as any).status || ''
          if (completed != null && total != null && total > 0) {
            const pct = Math.round((completed / total) * 100)
            setPullProgress(`${pStatus} ${pct}%`)
          } else {
            setPullProgress(pStatus)
          }
          break
        }

        case 'pull_done': {
          const pulledModel = (msg as any).model || pulling
          setPulling(null)
          setPullProgress('')
          // Auto-switch to the newly downloaded model and close picker.
          if (pulledModel) {
            void window.api.applicationCommand('ChangeModel', { modelId: pulledModel })
            setShowPicker(false)
          }
          // Refresh catalog to update installed status.
          window.api.sendToPython({ id: nextId(), type: 'catalog' })
          break
        }

        case 'delete_done':
          // Refresh catalog.
          window.api.sendToPython({ id: nextId(), type: 'catalog' })
          break

        case 'update_available':
          setUpdateAvailable(true)
          setUpdateMessage(msg.message || 'Update available')
          break

        case 'updating':
          setAppUpdating(true)
          break

        case 'api_key_set':
          setHasClaude(!!(msg as any).has_claude)
          break

        case 'update_done': {
          setAppUpdating(false)
          const d = msg as any
          if (d.success) {
            setUpdateAvailable(false)
            setAppUpdateResult(d.message || 'Updated successfully. Restart to apply.')
          } else {
            setAppUpdateResult(d.message || 'Update failed.')
          }
          break
        }
      }
    })

    // Signal to main process that renderer is ready to receive messages.
    // The host sends its current snapshot projection without restarting work.
    window.api.signalReady()

    return cleanup
  }, [])

  const sendMessage = useCallback((text: string) => {
    if (!text.trim()) return
    void window.api.applicationCommand('SubmitUserInput', { content: text })
  }, [])

  const handleStop = useCallback(() => {
    if (view?.activeTurnId) void window.api.applicationCommand('CancelTurn', { turnId: view.activeTurnId })
  }, [view?.activeTurnId])

  const answerAskUser = useCallback(() => {
    if (askReq) void window.api.applicationCommand('ResolveUserInput', {
      inputRequestId: askReq.inputRequestId, response: askAnswer,
    })
  }, [askReq, askAnswer])

  const resolveApproval = useCallback((approved: boolean) => {
    if (!confirmReq) return
    const { approvalId, toolCallId, requestDigest, cwd, policyRevision } = confirmReq
    void window.api.applicationCommand('ResolveApproval', {
      approvalId, toolCallId, requestDigest, cwd, policyRevision, approved,
    })
  }, [confirmReq])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ignore key events during IME composition (e.g. Japanese input).
    if (e.nativeEvent.isComposing || e.keyCode === 229) return

    if (e.key === 'Escape' && streaming) {
      e.preventDefault()
      handleStop()
      return
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (streaming) {
        // Stop current stream first; user can then send their message.
        handleStop()
        return
      }
      sendMessage(inputText)
      setInputText('')
    }
  }, [inputText, sendMessage, streaming, handleStop])

  const handleModelSelect = useCallback((model: string) => {
    setShowPicker(false)
    // The backend confirms the change or returns an explicit conflict.
    void window.api.applicationCommand('ChangeModel', { modelId: model })
  }, [])

  const handlePull = useCallback((model: string) => {
    setPulling(model)
    setPullProgress('starting...')
    window.api.sendToPython({ id: nextId(), type: 'pull_model', model })
  }, [])

  const handleUpdateCatalog = useCallback(() => {
    window.api.sendToPython({ id: nextId(), type: 'update_catalog' })
  }, [])

  const handleSearch = useCallback((query: string, sort: string, capability: string) => {
    setSearching(true)
    window.api.sendToPython({ id: nextId(), type: 'search_models', query, sort, capability })
  }, [])

  const handleDelete = useCallback((model: string) => {
    window.api.sendToPython({ id: nextId(), type: 'delete_model', model })
  }, [])

  const handleRecommend = useCallback(() => {
    window.api.sendToPython({ id: nextId(), type: 'recommend' })
  }, [])

  const handleClear = useCallback(() => {
    void window.api.applicationCommand('ExecuteCommand', { name: 'clear' })
  }, [])

  const handleAppUpdate = useCallback(() => {
    setAppUpdating(true)
    setAppUpdateResult('')
    window.api.sendToPython({ id: nextId(), type: 'do_update' })
  }, [])

  const handleProviderSwitch = useCallback((provider: string) => {
    void window.api.applicationCommand('ChangeProvider', { providerId: provider })
  }, [])

  const handleFileSelect = useCallback((path: string) => {
    setSelectedFile(path)
  }, [])

  const handleRootChange = useCallback((path: string) => {
    setSelectedFile(null)
    // Notify Python server to change working directory.
    window.api.sendToPython({ id: nextId(), type: 'set_cwd', path })
  }, [])

  const handleInput = useCallback(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }, [])

  const statusDotClass = status.ready ? 'on' : status.connected ? 'wait' : 'off'

  return (
    <div className="app">
      <div className="titlebar">
        <span className="titlebar-text">local-cli</span>
        {import.meta.env.DEV && <span className="titlebar-dev">DEV</span>}
      </div>

      <div className="statusbar">
        <div className="status-item">
          <div className={`status-dot ${statusDotClass}`} />
          <span>{status.ready ? 'ready' : 'connecting...'}</span>
        </div>
        <div className="status-item model-status-group">
          <span
            className="model-select"
            onClick={() => { if (!streaming && status.ready) { refreshCatalog(); setShowPicker(true) } }}
          >
            {status.model || '...'}
          </span>
          <div className="model-hover-card">
            <div className="model-hover-name">{status.model}</div>
            <div className="model-hover-desc">
              {catalog?.models.find(m => m.name === status.model || m.name === status.model.split(':')[0])?.description
                || 'Local model via Ollama'}
            </div>
            <div className="model-hover-hint">Click model name to switch</div>
          </div>
        </div>
        <div className="status-item">
          <ProviderSelector
            currentProvider={status.provider}
            hasClaude={hasClaude}
            disabled={streaming || !status.ready}
            onSwitch={handleProviderSwitch}
            onLoginRequest={() => setShowClaudeLogin(true)}
          />
        </div>
        <div className="status-spacer" />
        {pulling && (
          <div className="status-item">
            <span style={{ color: 'var(--yellow)' }}>pulling {pulling}...</span>
          </div>
        )}
        <div className="status-item">
          <span style={{ color: 'var(--text-muted)' }}>{status.tools.length} tools</span>
        </div>
        <button
          className={`status-btn ${explorerOpen ? 'active' : ''}`}
          onClick={() => setExplorerOpen(v => !v)}
          title="Toggle file explorer (Cmd+B)"
        >files</button>
        <button
          className="status-btn"
          onClick={() => setShowSettings(true)}
          title="Settings (Cmd+,)"
        >settings</button>
        {messages.length > 0 && (
          <button className="status-btn" disabled={streaming || !status.ready} onClick={handleClear}>clear</button>
        )}
      </div>

      {autoUpdateProgress && (
        <div className="update-bar">
          <span className="update-bar-text">
            {autoUpdateProgress.stage === 'downloading'
              ? `Downloading v${autoUpdateProgress.version || '?'}... ${autoUpdateProgress.percent}%`
              : autoUpdateProgress.stage === 'extracting'
              ? 'Extracting...'
              : autoUpdateProgress.stage === 'installing'
              ? 'Installing... app will restart'
              : `Updating to v${autoUpdateProgress.version || '?'}...`}
          </span>
          <div className="update-bar-progress">
            <div className="update-bar-fill" style={{ width: `${autoUpdateProgress.percent}%` }} />
          </div>
        </div>
      )}

      {!autoUpdateProgress && (updateAvailable || appUpdateResult) && (
        <div className="update-bar">
          {appUpdating ? (
            <span className="update-bar-text">Updating...</span>
          ) : appUpdateResult ? (
            <>
              <span className="update-bar-text">{appUpdateResult}</span>
              <button className="update-bar-dismiss" onClick={() => setAppUpdateResult('')}>dismiss</button>
            </>
          ) : (
            <>
              <span className="update-bar-text">{updateMessage}</span>
              <button className="update-bar-btn" onClick={handleAppUpdate}>Install update</button>
              <button className="update-bar-dismiss" onClick={() => setUpdateAvailable(false)}>later</button>
            </>
          )}
        </div>
      )}

      {view?.error && <div className="confirm-bar" role="alert">
        <span>{view.error.code}: {view.error.message}</span>
        {!status.connected && <button className="confirm-approve" onClick={() => void window.api.restartBackend()}>Restart backend</button>}
      </div>}
      {view?.gap && <div className="resume-bar" role="status">Event continuity was interrupted; the current session snapshot is authoritative.</div>}

      <div className="app-body">
        {explorerOpen && (
          <div className="explorer-pane">
            <FileExplorer
              rootDir={rootDir}
              onFileSelect={handleFileSelect}
              onRootChange={handleRootChange}
              refreshKey={explorerRefreshKey}
            />
          </div>
        )}

        <div className="chat-pane">
          <div className="terminal" ref={terminalRef} onClick={handleTerminalClick}>
            <div className="terminal-inner">
              {messages.length === 0 ? (
                <div className="welcome">
                  <Banner version={appVersion} />
                  <div className="welcome-sub">
                    Local AI coding agent powered by Ollama.
                    Read, write, edit files. Run commands. Search code.
                  </div>
                  {status.model && (
                    <div className="model-info-block">
                      <span className="model-info-name">{status.model}</span>
                      <span className="model-info-desc">
                        {catalog?.models.find(m => m.name === status.model || m.name === status.model.split(':')[0])?.description
                          || 'Local model via Ollama'}
                      </span>
                    </div>
                  )}
                  <div className="welcome-hint">
                    Type a message below to start. Shift+Enter for newline.
                  </div>
                  {resumable && (
                    <div className="resume-bar">
                      <span className="resume-text">
                        Previous conversation ({resumable.count} messages)
                        {resumable.preview ? ` — “${resumable.preview}”` : ''}
                      </span>
                      <button
                        className="resume-btn"
                        onClick={() => void window.api.applicationCommand('ExecuteCommand', { name: 'resume' })}
                      >
                        Restore
                      </button>
                      <button
                        className="resume-dismiss"
                        onClick={() => setResumeDismissed(true)}
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                messages.map(msg => <MessageBlock key={msg.id} message={msg} />)
              )}
            </div>
          </div>

          {confirmReq && (
            <div className="confirm-bar">
              <div className="confirm-text">
                <span className="confirm-label">Risky command — approve?</span>
                <code className="confirm-command">{String(confirmReq.arguments.command || confirmReq.name)}</code>
              </div>
              <button
                className="confirm-deny"
                onClick={() => resolveApproval(false)}
              >
                Deny
              </button>
              <button
                className="confirm-approve"
                onClick={() => resolveApproval(true)}
              >
                Run it
              </button>
            </div>
          )}

          {askReq && (
            <div className="confirm-bar">
              <div className="confirm-text">
                <span className="confirm-label">Agent question</span>
                <span>{askReq.question}</span>
              </div>
              <input
                aria-label="Answer to agent"
                value={askAnswer}
                onChange={e => setAskAnswer(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') answerAskUser() }}
              />
              <button className="confirm-approve" onClick={answerAskUser}>Send</button>
              <button className="confirm-deny" onClick={handleStop}>Stop</button>
            </div>
          )}

          <div className="input-area">
            <div className="input-row">
              <span className="input-marker">&gt;</span>
              <textarea
                ref={inputRef}
                className="input-field"
                value={inputText}
                onChange={e => { setInputText(e.target.value); handleInput() }}
                onKeyDown={handleKeyDown}
                placeholder={
                  !status.ready ? 'waiting for backend...'
                  : streaming ? 'Enter to stop, Esc to cancel...'
                  : 'ask anything...'
                }
                disabled={!status.ready}
                rows={1}
              />
              {streaming && (
                <button className="stop-btn" onClick={handleStop} title="Cancel current turn (Esc)">
                  stop
                </button>
              )}
            </div>
          </div>
        </div>

        {selectedFile && (
          <div className="viewer-pane">
            <FileViewer
              filePath={selectedFile}
              onClose={() => setSelectedFile(null)}
            />
          </div>
        )}
      </div>

      {showPicker && (
        <ModelPicker
          catalog={catalog}
          searchResults={searchResults}
          current={status.model}
          onSelect={handleModelSelect}
          onPull={handlePull}
          onDelete={handleDelete}
          onSearch={handleSearch}
          onUpdate={handleUpdateCatalog}
          onClose={() => setShowPicker(false)}
          pulling={pulling}
          pullProgress={pullProgress}
          searching={searching}
          updating={updating}
          recommendations={recommendations}
          systemInfo={systemInfo}
          onRequestRecommend={handleRecommend}
        />
      )}

      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} backendGitCapability={backendGitCapability}
          rag={view?.rag} ragProgress={view?.ragProgress || ''} ragResult={view?.ragResult || null}
          onRAGEnabled={enabled => void window.api.applicationCommand('SetRAGEnabled', { enabled })}
          onRAGQuery={query => void window.api.applicationCommand('QueryRAG', { query })} />
      )}

      {showClaudeLogin && (
        <ClaudeLogin
          onClose={() => setShowClaudeLogin(false)}
          onAuthenticated={(method) => {
            setHasClaude(true)
            setClaudeAuthMethod(method)
            setShowClaudeLogin(false)
          }}
          isAuthenticated={hasClaude}
          authMethod={claudeAuthMethod}
        />
      )}
    </div>
  )
}
