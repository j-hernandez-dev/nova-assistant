import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react'
import type { PythonMessage, ProjectAction, ProjectState } from './types'
import { recheckBackend } from './backend_recovery'
import { useSessionView } from './use_session_view'
import { NovaIcon } from './components/NovaIcon'
import { QuestionModal } from './components/QuestionModal'
import { usePresence } from './use_presence'
import { NovaOrbit } from './components/NovaOrbit'
import { ReadinessNotice } from './components/ReadinessNotice'
import { ModelDownloadNotice } from './components/ModelDownloadNotice'
import { useI18n } from './i18n'
import { ConversationHistory } from './components/ConversationHistory'
import { resizePrompt } from './prompt_layout'
import { ConversationTurn } from './components/ConversationTurn'
import { ActivityChain } from './components/TurnActivity'
import { collectActions, conversationGroups } from './turn_activity'
import { sameProjectPath, validProjectState, fileBasename } from './project_presentation'
import { applicationErrorKey, openApprovalReview, representedActivityError } from './activity_presentation'
import { ModelPicker } from './components/ModelPicker'
import { ModelSelector } from './components/ModelSelector'
import { ModelOperations } from './model_operations'
import { FileExplorer } from './components/FileExplorer'
import { ProviderSelector } from './components/ProviderSelector'
import { FileViewer } from './components/FileViewer'
import { SettingsPanel, type SettingsSection } from './components/SettingsPanel'
import { ChatSettings, type ProjectChat } from './components/ChatSettings'
import { ContextSettings } from './components/ContextSettings'
import { WebSettings, ObservedValue, SettingsCode } from './components/WebSettings'
import { MemorySettings } from './components/MemorySettings'
import { KnowledgeSettings } from './components/KnowledgeSettings'
import { ClaudeLogin } from './components/ClaudeLogin'

let reqIdCounter = 0
function nextId() { return ++reqIdCounter }

export default function App() {
  const { t, localeError } = useI18n()
  const [activeView, setActiveView] = useState<'home' | 'history'>('home')
  const view = useSessionView()
  const messages = view?.messages || []
  const status = view?.status || { model: '', provider: '', connected: false, tools: [], ready: false }
  useLayoutEffect(() => { document.documentElement.setAttribute('data-nova-startup', 'mounted') }, [])
  useEffect(() => {
    // Protocol readiness or an inspectable startup error reveals the ordinary UI.
    // Ollama availability is handled by its existing setup notice.
    if (view?.status.ready || view?.error) document.documentElement.setAttribute('data-nova-startup', 'ready')
  }, [view?.status.ready, view?.error])
  const streaming = !!view?.activeTurnId
  const confirmReq = view?.approvals[0] || null
  const [approvalReviewError, setApprovalReviewError] = useState(false)
  const approvalReviewRevision = useRef(0)
  const toolActivities = view?.toolActivities || []
  const groups = conversationGroups(messages, toolActivities)
  const latestGroup = groups[groups.length - 1]
  const approvalToolCallIds = (view?.approvals || []).map(approval => approval.toolCallId)
  const associatedActivityIds = new Set(messages.flatMap(message => (message.toolActivities || []).map(activity => activity.operationId)))
  const groupedActivityIds = new Set(groups.flatMap(group => group.activities.map(activity => activity.operationId)))
  const orphanActivities = toolActivities.filter(activity => !associatedActivityIds.has(activity.operationId) && !groupedActivityIds.has(activity.operationId))
  const errorHasActivity = representedActivityError(view?.error, toolActivities)
  const askReq = view?.inputs[0] || null
  const [showPicker, setShowPicker] = useState(false)
  const [modelOperations] = useState(() => new ModelOperations(
    message => window.api.sendToPython(message), nextId,
    () => { void window.api.refreshReadiness().catch(() => {}) },
  ))
  const [modelState, setModelState] = useState(modelOperations.state)
  const { catalog, pulling, pullProgress, searchResults, searching, recommendations, systemInfo, updating } = modelState
  const download = view?.modelDownload || null
  const downloadBusy = !!download && !['failed', 'complete'].includes(download.phase) || !!pulling
  useEffect(() => { if (downloadBusy) { setShowPicker(false); setShowClaudeLogin(false) } }, [downloadBusy])
  useEffect(() => { if (download?.phase === 'complete') modelOperations.refreshCatalog() }, [download?.id, download?.phase, modelOperations])
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const [updateMessage, setUpdateMessage] = useState('')
  const [appUpdating, setAppUpdating] = useState(false)
  const [appUpdateResult, setAppUpdateResult] = useState('')
  const [autoUpdateProgress, setAutoUpdateProgress] = useState<{ stage: string; percent: number; version?: string } | null>(null)
  const [explorerOpen, setExplorerOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const explorerPresent = usePresence(explorerOpen)
  const pickerPresent = usePresence(showPicker && !askReq && !confirmReq)
  const settingsPresent = usePresence(showSettings && !askReq && !confirmReq)
  const [chats,setChats]=useState<Array<{path:string;hasHistory:boolean;messageCount:number}>>([])
  const [chatsLoading,setChatsLoading]=useState(false)
  const [chatsError,setChatsError]=useState(false)
  const [chatRevision,setChatRevision]=useState(0)
  const [settingsSection,setSettingsSection]=useState<SettingsSection>('general')
  const [showClaudeLogin, setShowClaudeLogin] = useState(false)
  useEffect(() => { if (confirmReq || askReq) { setShowSettings(false); setShowPicker(false); setShowClaudeLogin(false) } }, [confirmReq?.approvalId, askReq?.inputRequestId])
  const [claudeAuthMethod, setClaudeAuthMethod] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [hasClaude, setHasClaude] = useState(false)
  const [projects, setProjects] = useState<ProjectState | null>(null)
  const [projectErrorCode, setProjectErrorCode] = useState<string | null>(null)
  const [projectActionPending, setProjectActionPending] = useState(false)
  const [projectPreviewRevision, setProjectPreviewRevision] = useState(0)
  const projectRequestRevision = useRef(0)
  const projectActionLocked = useRef(false)
  const rootDir = projects?.activePath || null
  const [selectedFileRoot, setSelectedFileRoot] = useState<string | null>(null)
  const [appVersion, setAppVersion] = useState('')
  const [backendGitCapability, setBackendGitCapability] = useState<'UNAVAILABLE' | 'AVAILABLE_NOT_REPOSITORY' | 'AVAILABLE_REPOSITORY' | null>(null)
  const explorerRefreshKey = (view?.fileRevision || 0) + projectPreviewRevision
  const terminalRef = useRef<HTMLDivElement>(null)
  const followOutputRef = useRef(true)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [selectedSources,setSelectedSources] = useState<string[]>([])
  const [inputText, setInputText] = useState('')
  const [modelSelectionError, setModelSelectionError] = useState(false)
  const [pendingModel, setPendingModel] = useState<string | null>(null)
  const [modelSelectionAccepted, setModelSelectionAccepted] = useState(false)
  const [submitError, setSubmitError] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [sentFeedback, setSentFeedback] = useState<{ id: number; text: string } | null>(null)
  const sendFeedbackRevision = useRef(0)
  useEffect(() => {
    if (!sentFeedback) return
    const timer = setTimeout(() => setSentFeedback(null), 1000)
    return () => clearTimeout(timer)
  }, [sentFeedback])
  const submittingRef = useRef(false)
  const [historyViewError, setHistoryViewError] = useState(false)
  const conversation = view?.conversation
  const unreadCount = conversation?.unreadCount || 0
  const chatTitle = `${t('projectChat')} · ${fileBasename(view?.workspace || rootDir || '')}`
  const visibleChats:ProjectChat[]=(projects?.folders || []).map(folder=>({...folder,
    active:sameProjectPath(folder.path,view?.workspace),hasHistory:chats.find(chat=>sameProjectPath(chat.path,folder.path))?.hasHistory || false,
    messageCount:chats.find(chat=>sameProjectPath(chat.path,folder.path))?.messageCount || 0}))
  const chatWorkspace=useRef<string|null>(null)
  useEffect(()=>{if(!conversation?.hasConversation && !streaming)setActiveView('home')},[conversation?.hasConversation,streaming])
  useEffect(()=>{
    if(!view?.workspace || !view.status.ready)return
    if(chatWorkspace.current && !sameProjectPath(chatWorkspace.current,view.workspace))setActiveView(view.conversation.hasConversation?'history':'home')
    chatWorkspace.current=view.workspace
  },[view?.workspace,view?.status.ready,view?.conversation.hasConversation])
  useEffect(()=>{
    if(!showSettings || !status.ready || streaming || downloadBusy)return
    let active=true;setChatsLoading(true);setChatsError(false)
    void window.api.getProjectChats().then(result=>{
      if(!active)return
      if(!result.success || !Array.isArray(result.chats)){setChatsError(true);return}
      setChats(result.chats.filter(chat=>typeof chat.path==='string' && typeof chat.hasHistory==='boolean' && Number.isInteger(chat.messageCount)))
    }).catch(()=>{if(active)setChatsError(true)}).finally(()=>{if(active)setChatsLoading(false)})
    return()=>{active=false}
  },[showSettings,status.ready,streaming,downloadBusy,view?.workspace,projects?.folders,chatRevision])
  const readiness = view?.readiness
  const readinessReason = readiness ? readiness.reason : (status.connected ? 'CHECKING' : 'BACKEND_DISCONNECTED')
  const installedModels = readiness?.installedModels.map(model => model.name) || []
  const loadingInstalledModels = readinessReason === 'CHECKING' && installedModels.length === 0
  const systemReady = !!readiness?.ready && status.connected && !pendingModel && !downloadBusy

  useEffect(() => modelOperations.subscribe(setModelState), [modelOperations])
  useEffect(() => () => modelOperations.dispose(), [modelOperations])
  const modelBackendWasConnected = useRef(false)
  useEffect(() => {
    if (modelBackendWasConnected.current && !status.connected) modelOperations.disconnected()
    modelBackendWasConnected.current = status.connected
  }, [status.connected, modelOperations])

  useEffect(() => {
    if (pendingModel && modelSelectionAccepted && status.model === pendingModel) {
      setPendingModel(null)
      setModelSelectionAccepted(false)
      setShowPicker(false)
    }
  }, [pendingModel, modelSelectionAccepted, status.model])

  useEffect(() => {
    if (!status.connected && pendingModel) {
      setPendingModel(null)
      setModelSelectionAccepted(false)
      setModelSelectionError(true)
    }
  }, [status.connected, pendingModel])

  useEffect(() => {
    if (pendingModel && modelSelectionAccepted && view?.error?.code === 'MODEL_SELECTION_NOT_CONFIRMED') {
      setPendingModel(null)
      setModelSelectionAccepted(false)
      setModelSelectionError(true)
    }
  }, [pendingModel,modelSelectionAccepted,view?.error?.code])

  const scrollToBottom = useCallback(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    let active = true
    setHistoryViewError(false)
    void window.api.setHistoryVisible(activeView === 'history').then(result => {
      if (active && !result.success) setHistoryViewError(true)
    }).catch(() => { if (active) setHistoryViewError(true) })
    return () => {
      active = false
      // Closing a view changes presentation only; backend work continues.
      void window.api.setHistoryVisible(false).catch(() => {})
    }
  }, [activeView])

  useEffect(() => {
    if (activeView !== 'history') return
    followOutputRef.current = true
    scrollToBottom()
  }, [activeView,scrollToBottom])

  useEffect(() => {
    if (activeView === 'history' && followOutputRef.current) scrollToBottom()
  }, [messages,activeView,scrollToBottom])

  const handleHistoryScroll = useCallback(() => {
    const element = terminalRef.current
    if (element) followOutputRef.current = element.scrollHeight - element.scrollTop - element.clientHeight <= 80
  }, [])

  useEffect(() => { approvalReviewRevision.current += 1; setApprovalReviewError(false) }, [confirmReq?.approvalId])
  useEffect(() => {
    const request = ++projectRequestRevision.current
    void (async () => {
      try {
        const state = await window.api.getProjects()
        if (request !== projectRequestRevision.current) return
        if (!validProjectState(state)) { setProjectErrorCode('PROJECT_UNAVAILABLE'); return }
        setProjects(state)
        setProjectErrorCode(state.error?.code || null)
      } catch { if (request === projectRequestRevision.current) setProjectErrorCode('PROJECT_UNAVAILABLE') }
    })()
    return () => { projectRequestRevision.current += 1 }
  }, [view?.workspace])
  useEffect(() => { setSelectedFile(null); setSelectedFileRoot(null) }, [rootDir])
  useEffect(() => {
    if (typeof window.api.onProjectsChanged !== 'function') return
    return window.api.onProjectsChanged(state => {
      if (!validProjectState(state)) return
      projectRequestRevision.current += 1
      setProjects(state)
      setProjectErrorCode(state.error?.code || null)
    })
  }, [])

  // Initialize host metadata on mount.
  useEffect(() => {
    if (!window.api) return
    window.api.getAppVersion().then(setAppVersion)
    window.api.hasClaudeAccess().then(setHasClaude)
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
        if (document.querySelector('.nova-question-pending')) return
        e.preventDefault()
        setShowPicker(false)
        setShowClaudeLogin(false)
        setSettingsSection('general'); setShowSettings(prev => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Cmd/Ctrl+B keyboard shortcut to toggle file explorer.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        if (document.querySelector('.nova-question-pending')) return
        e.preventDefault()
        setExplorerOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleTerminalClick = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target instanceof Element && event.target.closest('a,button,details,summary,input,textarea,select,[role="button"],[contenteditable="true"]')) return
    // Don't steal focus if the user is selecting text for copy.
    const sel = window.getSelection()
    if (sel && sel.toString().length > 0) return
    inputRef.current?.focus()
  }, [])

  const refreshCatalog = useCallback(() => {
    modelOperations.refreshCatalog()
  }, [modelOperations])

  // Listen to Python messages.
  useEffect(() => {
    if (!window.api) return

    const cleanup = window.api.onPythonMessage((msg: PythonMessage) => {
      modelOperations.receive(msg)
      switch (msg.type) {
        case 'ready':
          setBackendGitCapability(msg.backend_git_capability || null)
          // Read has_claude from ready message.
          if (msg.has_claude !== undefined) {
            setHasClaude(!!msg.has_claude)
          }
          modelOperations.backendReady()
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
  }, [modelOperations])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || !systemReady || streaming || submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    setSubmitError(false)
    const attachmentRefs=(view?.knowledge?.attachmentRefs || []).filter(r => selectedSources.includes(r.sourceId))
    try {
      const receipt = await window.api.applicationCommand('SubmitUserInput', { content: text, attachmentRefs })
      if (receipt.accepted) {
        setSelectedSources([])
        setSentFeedback({ id: ++sendFeedbackRevision.current, text: inputRef.current?.value === text ? text : '' })
        setInputText(current => current === text ? '' : current)
      } else setSubmitError(true)
    } catch { setSubmitError(true) }
    finally { submittingRef.current = false; setSubmitting(false) }
  }, [view?.knowledge?.attachmentRefs,selectedSources,systemReady,streaming])

  const handleStop = useCallback(() => {
    if (view?.activeTurnId) void window.api.applicationCommand('CancelTurn', { turnId: view.activeTurnId })
  }, [view?.activeTurnId])

  const reviewApproval = useCallback(async () => {
    if (!confirmReq) return
    const revision = ++approvalReviewRevision.current
    const opened = await openApprovalReview(() => window.api.reviewPendingApproval())
    if (revision === approvalReviewRevision.current) setApprovalReviewError(!opened)
  }, [confirmReq?.approvalId])

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
      void sendMessage(inputText)
    }
  }, [inputText, sendMessage, streaming, handleStop])

  const handleModelSelect = useCallback(async (model: string) => {
    if (downloadBusy || streaming || pendingModel || !status.ready) return
    setModelSelectionError(false)
    if (model === status.model) { setShowPicker(false); return }
    setPendingModel(model)
    setModelSelectionAccepted(false)
    try {
      const receipt = await window.api.applicationCommand('ChangeModel', { modelId: model })
      if (!receipt.accepted) {
        setPendingModel(null)
        setModelSelectionError(true)
        return
      }
      setModelSelectionAccepted(true)
    } catch {
      setPendingModel(null)
      setModelSelectionAccepted(false)
      setModelSelectionError(true)
    }
  }, [downloadBusy,streaming,pendingModel,status.ready,status.model])

  const handlePull = useCallback((model: string) => {
    if (downloadBusy || streaming || projectActionPending || pendingModel || !status.ready) return
    if (modelOperations.pull(model)) setShowPicker(false)
  }, [modelOperations,downloadBusy,streaming,projectActionPending,pendingModel,status.ready])

  const handleUpdateCatalog = useCallback(() => {
    modelOperations.sync()
  }, [modelOperations])

  const handleSearch = useCallback((query: string, sort: string, capability: string) => {
    modelOperations.search(query, sort, capability)
  }, [modelOperations])

  const handleDelete = useCallback((model: string) => {
    modelOperations.delete(model)
  }, [modelOperations])

  const handleRecommend = useCallback(() => {
    modelOperations.recommend()
  }, [modelOperations])

  const handleClearHistory = useCallback(async (path?:string) => {
    const result = await window.api.clearProjectChat(path)
    if(result.success)setChatRevision(revision=>revision+1)
    return result
  }, [])

  const handleAppUpdate = useCallback(() => {
    setAppUpdating(true)
    setAppUpdateResult('')
    window.api.sendToPython({ id: nextId(), type: 'do_update' })
  }, [])

  const handleProviderSwitch = useCallback((provider: string) => {
    if (downloadBusy || streaming || pendingModel || !status.ready) return
    setModelSelectionError(false)
    void window.api.applicationCommand('ChangeProvider', { providerId: provider }).then(receipt => {
      if (!receipt.accepted) setModelSelectionError(true)
    }).catch(() => setModelSelectionError(true))
  }, [downloadBusy,streaming,pendingModel,status.ready])

  const openReadinessConfiguration = useCallback(() => {
    if (downloadBusy) return
    if (readiness?.requiredAction === 'SELECT_MODEL') {
      setShowSettings(false)
      setShowClaudeLogin(false)
      refreshCatalog()
      setShowPicker(true)
    } else if (readiness?.requiredAction === 'CONFIGURE_PROVIDER') {
      setSettingsSection('connection'); setShowPicker(false); setShowSettings(true)
    }
  }, [downloadBusy,readiness?.requiredAction,refreshCatalog])

  const handleFileSelect = useCallback((path: string) => {
    if (!rootDir) return
    setSelectedFileRoot(rootDir)
    setSelectedFile(path)
  }, [rootDir])

  const handleProjectAction = useCallback(async (action: ProjectAction, path?: string) => {
    if (downloadBusy || projectActionLocked.current) return
    projectActionLocked.current = true
    setProjectActionPending(true)
    setProjectErrorCode(null)
    // Invalidate older refreshes; only a host-confirmed transaction changes the root.
    projectRequestRevision.current += 1
    try {
      const result = await window.api.projectAction(action, path)
      projectRequestRevision.current += 1
      if (!validProjectState(result?.state)) { setProjectErrorCode('PROJECT_UNAVAILABLE'); return }
      setProjects(result.state)
      if (!result.success && !result.canceled) setProjectErrorCode(result.error?.code || 'PROJECT_ACTION_FAILED')
      else setProjectErrorCode(result.state.error?.code || null)
    } catch { setProjectErrorCode('PROJECT_ACTION_FAILED') }
    finally {
      projectActionLocked.current = false; setProjectActionPending(false)
      // An in-flight preview may have been invalidated while the host picker
      // was open. Refresh reads once after settlement, including cancellation.
      setProjectPreviewRevision(revision => revision + 1)
    }
  }, [downloadBusy])

  useLayoutEffect(() => { if (inputRef.current) resizePrompt(inputRef.current) }, [inputText, t])
  useEffect(() => {
    const element = inputRef.current
    if (!element) return
    let width = -1
    const observer = new ResizeObserver(entries => {
      const current = entries[0]?.contentRect.width
      if (current !== undefined && current !== width) { width = current; resizePrompt(element) }
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="app nova-app">
      <nav className="nova-rail" aria-label="Nova">
        <button className={`nova-nav-button ${explorerOpen ? 'active' : ''}`}
          title={`${t('projects')} (Ctrl+B)`} aria-label={t('projects')} aria-expanded={explorerOpen}
          onClick={() => setExplorerOpen(v => !v)}><NovaIcon name="folder" size={28} /></button>
        <button className={`nova-nav-button ${showPicker ? 'active' : ''}`}
          title={downloadBusy ? t('modelDownloadBusy') : t('models')} aria-label={t('models')} aria-haspopup="dialog" disabled={downloadBusy}
          onClick={() => { setShowSettings(false); setShowClaudeLogin(false); refreshCatalog(); setShowPicker(true) }}>
          <NovaIcon name="brain" size={28} /></button>
        <div className="nova-rail-spacer" />
        <button className={`nova-nav-button ${showSettings ? 'active' : ''}`}
          title={`${t('settings')} (Ctrl+,)`} aria-label={t('settings')} aria-haspopup="dialog"
          onClick={() => { setShowPicker(false); setShowClaudeLogin(false); setSettingsSection('general'); setShowSettings(true) }}>
          <NovaIcon name="settings" size={28} /></button>
      </nav>

      <div className="nova-workspace">
        <div className="nova-main">
        {explorerPresent && (
          <aside className="explorer-pane nova-project-pane" data-exiting={!explorerOpen || undefined}
            inert={!explorerOpen} aria-hidden={!explorerOpen || undefined} aria-label={t('projects')}>
            <FileExplorer
              projects={projects}
              busy={downloadBusy || projectActionPending || streaming || !!view?.approvals.length || !!view?.inputs.length}
              errorCode={projectErrorCode}
              onFileSelect={handleFileSelect}
              onProjectAction={handleProjectAction}
              refreshKey={explorerRefreshKey}
            />
          </aside>
        )}

        <main className="chat-pane" aria-label={activeView === 'home' ? t('home') : chatTitle}>
          <header className="nova-header">
            <div className="nova-history-title">{activeView === 'history' ? chatTitle : ''}</div>
            <div className="nova-header-actions">
              {conversation?.hasConversation && <button className="nova-icon-button nova-history-button" title={activeView === 'home' ? t('openProjectChat') : t('home')}
                aria-label={activeView === 'home' && unreadCount > 0
                  ? `${t('openProjectChat')}: ${unreadCount} ${t('unreadResponses')}` : activeView === 'home' ? t('openProjectChat') : t('home')}
                onClick={() => setActiveView(current => current === 'home' ? 'history' : 'home')}>
                <NovaIcon name={activeView === 'home' ? 'history' : 'back'} />
                {activeView === 'home' && unreadCount > 0 && <span className="nova-unread-badge" aria-hidden="true">
                  {unreadCount > 99 ? '99+' : unreadCount}</span>}
              </button>}
              <div className="nova-status-pill" role="status">
                <span className={`status-dot ${systemReady ? 'on' : 'off'}`} />
                {downloadBusy ? t(download?.phase === 'refreshing' || download?.phase === 'refresh-failed' ? 'modelDownloadUpdating' : 'modelDownloadStatus') : systemReady ? t('systemReady') : t('systemNotReady')}
              </div>
            </div>
          </header>

          {activeView === 'home' ? (
            <div key="home" className="nova-home nova-view-enter">
              <NovaOrbit />
              {latestGroup && (streaming || latestGroup.activities.length > 0) && <section className="nova-home-activity" aria-label={t('activity')}>
                <ConversationTurn key={latestGroup.id} group={latestGroup} activeTurnId={view?.activeTurnId} compact
                  approvalToolCallIds={approvalToolCallIds} />
              </section>}
            </div>
          ) : (
            <div key="history" className="terminal nova-conversation nova-view-enter" ref={terminalRef} onClick={handleTerminalClick}
              onScroll={handleHistoryScroll} tabIndex={0} aria-label={chatTitle}>
              <div className="terminal-inner">
                {messages.length === 0 ? <p className="nova-home-caption">{t('historyEmpty')}</p>
                  : <ConversationHistory groups={groups} activeTurnId={view?.activeTurnId} approvalToolCallIds={approvalToolCallIds} />}
                {orphanActivities.length > 0 && <section className="nova-orphan-activities" aria-label={t('activity')}>
                  <ActivityChain actions={collectActions([], orphanActivities)} approvalToolCallIds={approvalToolCallIds} />
                </section>}
              </div>
            </div>
          )}

          <div className="nova-composer-area">
            {(historyViewError || conversation?.preferenceError) && <div className="nova-history-notice" role="status">{t('historyStateSaveFailed')}</div>}
            <ModelDownloadNotice download={download} onRetry={() => void window.api.retryModelDownloadInventory()} />
            {(!downloadBusy || !status.connected) && <ReadinessNotice ready={systemReady} reason={readinessReason}
              requiredAction={readiness?.requiredAction || null} modelChanging={!!pendingModel}
              onConfigure={openReadinessConfiguration} onRecheck={() => recheckBackend(status.connected, window.api)}
              />}
            {localeError && !showSettings && <div className="confirm-bar" role="alert">{t(localeError)}</div>}
            {modelSelectionError && !showPicker && <div className="confirm-bar" role="alert">{t('modelChangeFailed')}</div>}
            {submitError && <div className="confirm-bar" role="alert">{t('submitFailed')}</div>}
            {view?.modelPreferenceError && <div className="confirm-bar" role="alert">{t('modelPreferenceSaveFailed')}</div>}
            {view?.error && !errorHasActivity && view.error.code !== 'MODEL_SELECTION_NOT_CONFIRMED'
              && !(modelSelectionError && ['MODEL_UNAVAILABLE', 'INVALID_MODEL', 'INVALID_MODEL_INFO',
                'PROVIDER_UNAVAILABLE', 'PROVIDER_VALIDATION_FAILED', 'CONFLICT_ACTIVE_TURN'].includes(view.error.code)) && <div className="confirm-bar" role="alert">
              <div><span>{t(applicationErrorKey(view.error.code))}</span>
                <details className="nova-activity-diagnostics"><summary>{t('diagnosticDetails')}</summary><pre>{view.error.code}{'\n'}{view.error.message}</pre></details>
              </div>
            </div>}
            {view?.gap && <div className="resume-bar" role="status">{t('eventGap')}</div>}
            {view?.memoryNotice && <div className="resume-bar" role="status">{t('settingsMemoryRemoteNotice')}</div>}

            {confirmReq && <div className="nova-permission-pending" role="status">
              <span>{t('activityAwaitingPermission')}</span>
              <button onClick={() => void reviewApproval()}>{t('reviewPermission')}</button>
            </div>}
            {confirmReq && approvalReviewError && <p className="nova-permission-error" role="alert">{t('reviewPermissionFailed')}</p>}
            {askReq && <QuestionModal key={`${view?.sessionId}:${askReq.inputRequestId}`} />}

            <div className="nova-composer" data-submitting={submitting || undefined} data-sent={!!sentFeedback || undefined}>
              <button className="nova-attach-button" aria-label={t('attach')}
                title={view?.knowledge?.hostAcquisition ? t('attach') : t('attachmentsUnavailable')}
                disabled={downloadBusy || !status.ready || streaming || !view?.knowledge?.hostAcquisition}
                onClick={() => void window.api.knowledgePick()}><NovaIcon name="plus" /></button>
              <div className="nova-prompt-field" data-sent={(!inputText && !!sentFeedback) || undefined}>
              <textarea ref={inputRef} className="input-field nova-input" value={inputText}
                onChange={e => setInputText(e.target.value)} onKeyDown={handleKeyDown}
                placeholder={!status.connected ? t('waitingBackend') : streaming ? t('stopHint') : t('promptPlaceholder')}
                aria-label={t('promptPlaceholder')} rows={1} />
              {sentFeedback?.text && !inputText && <div className="nova-prompt-sent" key={sentFeedback.id} aria-hidden="true">{sentFeedback.text}</div>}
              </div>
              <ModelSelector models={installedModels} current={status.model} onSelect={handleModelSelect}
                title={status.provider === 'ollama' ? t('installedOllamaModels') : t('ollamaModelSelectorUnavailable')}
                disabled={downloadBusy || streaming || !!pendingModel || !status.ready || status.provider !== 'ollama' || showSettings || showPicker || !!askReq || !!confirmReq}
                placeholder={status.provider !== 'ollama' ? t('ollamaModelSelectorUnavailable')
                  : loadingInstalledModels ? t('loadingInstalledModels') : installedModels.length ? t('selectModel') : t('noInstalledModels')} />
              <button className="nova-send-button" aria-label={streaming ? t('stop') : t('send')}
                title={streaming ? t('stop') : t('send')} disabled={streaming ? !status.ready : !systemReady || submitting || !inputText.trim()}
                onClick={() => { if (streaming) handleStop(); else void sendMessage(inputText) }}>
                <NovaIcon name={streaming ? 'stop' : 'send'} /></button>
            </div>
            <div className="nova-composer-hint"><span role={sentFeedback ? 'status' : undefined} className={sentFeedback ? 'nova-send-feedback' : undefined}>
              {sentFeedback && <NovaIcon name="check" size={14} />}{t(sentFeedback ? 'messageSent' : 'composerHint')}</span>
            </div>


          </div>
        </main>

        {selectedFile && rootDir && sameProjectPath(selectedFileRoot, rootDir) && <div className="viewer-pane"><FileViewer key={`${rootDir}:${selectedFile}`} filePath={selectedFile} rootDir={rootDir} refreshKey={explorerRefreshKey} onClose={() => setSelectedFile(null)} /></div>}
        </div>
      </div>

      {pickerPresent && (
        <ModelPicker open={showPicker && !askReq && !confirmReq} catalog={catalog} searchResults={searchResults} current={status.model}
          onSelect={handleModelSelect} onPull={handlePull} onDelete={handleDelete} onSearch={handleSearch}
          onUpdate={handleUpdateCatalog} onClose={() => setShowPicker(false)} pulling={pulling}
          pullProgress={pullProgress} searching={searching} updating={updating} recommendations={recommendations}
           systemInfo={systemInfo} onRequestRecommend={handleRecommend} selectionError={modelSelectionError}
           selectionPending={!!pendingModel} actionsDisabled={downloadBusy || streaming || projectActionPending || !status.ready}
           catalogLoading={modelState.catalogLoading} catalogError={modelState.catalogError}
           searchError={modelState.searchError} recommendError={modelState.recommendError}
           recommending={modelState.recommending} operationError={modelState.operationError}
           operationNotice={modelState.operationNotice} deleting={modelState.deleting}
           operationUnconfirmed={modelState.mutationUnconfirmed} onRefreshCatalog={refreshCatalog}
           installedModels={readiness?.observedAt && !['OLLAMA_UNAVAILABLE', 'READINESS_CHECK_FAILED', 'READINESS_STALE', 'CHECKING'].includes(readiness.reason || '') ? installedModels : undefined} />
      )}

      {settingsPresent && (
        <SettingsPanel backendLocked={downloadBusy} open={showSettings && !askReq && !confirmReq} onClose={() => setShowSettings(false)} initialSection={settingsSection}
          chat={<ChatSettings disabled={downloadBusy || !status.ready || !!view?.recovering || streaming || !!view?.activeGenerationId || !!view?.approvals.length || !!view?.inputs.length || projectActionPending || !!projects?.busy}
            chats={visibleChats} loading={chatsLoading} error={chatsError} onClear={handleClearHistory}
            onOpen={path=>{setShowSettings(false);if(sameProjectPath(path,view?.workspace))setActiveView(conversation?.hasConversation?'history':'home');else void handleProjectAction('select',path)}} />}
          connection={<>
            <section className="nova-settings-card">
              <ObservedValue label={t('settingsCurrentProvider')} value={status.provider || t('settingsUnknown')} />
              <ObservedValue label={t('settingsCurrentModel')} value={status.model || t('settingsUnknown')} />
              <ObservedValue label={t(status.provider==='ollama'?'settingsOllama':'settingsObserved')} value={t(readiness?.ready ? 'systemReady' : 'systemNotReady')} />
              {!readiness?.ready && <p className="settings-hint">{t('finishSetup')}</p>}
              {readiness?.reason && <SettingsCode code={readiness.reason} />}
              <div className="settings-control-actions">
                <button className="settings-check-btn" disabled={downloadBusy} onClick={() => { setShowSettings(false); refreshCatalog(); setShowPicker(true) }}>{t('settingsOpenModels')}</button>
              </div>
            </section>
            <ContextSettings view={view} />
            <details className="nova-settings-card"><summary>{t('settingsAdvancedProvider')}</summary>
              <ProviderSelector currentProvider={status.provider} hasClaude={hasClaude}
                disabled={downloadBusy || streaming || !!pendingModel || !status.ready} onSwitch={handleProviderSwitch}
                onLoginRequest={() => { setShowPicker(false); setShowSettings(false); setShowClaudeLogin(true) }} />
            </details>
          </>}
          projects={<section className="nova-settings-card">
            <ObservedValue label={t('settingsCurrentProject')} value={rootDir || t('settingsNoProject')} />
            <ObservedValue label={t('settingsDefaultProject')} value={projects?.defaultPath || t('settingsUnknown')} />
            <p className="settings-hint">{t('settingsProjectHint')}</p>
            <button className="settings-check-btn" onClick={() => { setShowSettings(false); setExplorerOpen(true) }}>{t('settingsOpenProjects')}</button>
          </section>}
          web={<WebSettings key={`web:${view?.sessionId}:${rootDir}:${status.connected}`} view={view} />}
          memory={<MemorySettings key={`memory:${view?.sessionId}:${rootDir}:${status.connected}`} view={view} />}
          knowledge={<KnowledgeSettings key={`knowledge:${view?.sessionId}:${rootDir}:${status.connected}`} view={view} selectedSources={selectedSources} onSelectedSources={setSelectedSources} />}
          about={<>
            <section className="nova-settings-card">
              <ObservedValue label={t('backend')} value={t(status.connected ? 'settingsAvailable' : 'settingsUnavailable')} />
              <ObservedValue label={t('provider')} value={status.provider || t('settingsUnknown')} />
              <ObservedValue label={t('tools')} value={String(status.tools.length)} />
              <p className="settings-hint">{t('updatesNotConfigured')}</p>
              <p className="settings-hint">{t('settingsPrivacyHint')}</p>
            </section>
            <section className="nova-settings-card"><h3>{t('settingsDiagnostics')}</h3>
              <p className="settings-hint">{t('settingsDiagnosticsHint')}</p>
              <SettingsCode code={view?.error?.code || readiness?.reason || 'OK'} />
            </section>
          </>} />
      )}

      {showClaudeLogin && (
        <ClaudeLogin onClose={() => setShowClaudeLogin(false)} onAuthenticated={(method) => {
          setHasClaude(true); setClaudeAuthMethod(method); setShowClaudeLogin(false)
        }} isAuthenticated={hasClaude} authMethod={claudeAuthMethod} />
      )}
    </div>
  )
}
