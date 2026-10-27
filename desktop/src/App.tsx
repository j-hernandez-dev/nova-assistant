import { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react'
import type { PythonMessage, ProjectAction, ProjectState } from './types'
import { recheckBackend } from './backend_recovery'
import { useSessionView } from './use_session_view'
import { NovaIcon } from './components/NovaIcon'
import { QuestionModal } from './components/QuestionModal'
import { usePresence } from './use_presence'
import { useShortcuts } from './keyboard_shortcuts'
import { bindingFromEvent, type ShortcutAction } from '@nova/keyboard-shortcuts'
import { NovaMascot } from './components/NovaMascot'
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
import {ProjectPane} from './components/ProjectPane'
import {PromptSources} from './components/PromptSources'
import {SourceDropTarget} from './components/SourceDropTarget'
import {usePromptSources} from './use_prompt_sources'
import { LLMSettings } from './components/LLMSettings'
import { EmbeddingSettings } from './components/EmbeddingSettings'
import { useModelVisibility } from './model_visibility'
import { FileViewer } from './components/FileViewer'
import {MemoryItemViewer,SourceItemViewer} from './components/ProjectItemViewer'
import type {MemoryInspection} from './components/MemoryRecords'
import type {SourceFile} from '../shared/storage'
import { SettingsPanel, type SettingsSection } from './components/SettingsPanel'
import { ChatSettings, type ProjectChat } from './components/ChatSettings'
import { ProjectsSettings } from './components/ProjectsSettings'
import { WebSettings } from './components/WebSettings'
import {AboutRuntime} from './components/AboutSettings'
import { MemorySettings } from './components/MemorySettings'
import { StorageSettings } from './components/StorageSettings'
import { SourcesWindow } from './components/SourcesWindow'
import { MemoryWindow } from './components/MemoryWindow'
import { KnowledgeSettings } from './components/KnowledgeSettings'
import {useMemoryProposalNotifications} from './use_memory_proposal_notifications'

let reqIdCounter = 0
function nextId() { return ++reqIdCounter }

export default function App() {
  const { t, localeError, general } = useI18n()
  const shortcuts = useShortcuts()
  const modelVisibility = useModelVisibility()
  const shortcutTitle = (text: string, action: ShortcutAction) => shortcuts.label(action) ? `${text} (${shortcuts.label(action)})` : text
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
  const { catalog, pulling, pullProgress, recommendations, systemInfo, updating } = modelState
  const download = view?.modelDownload || null
  const downloadBusy = !!download && !['failed', 'complete'].includes(download.phase) || !!pulling
  useEffect(() => { if (downloadBusy) { setShowPicker(false); } }, [downloadBusy])
  useEffect(() => { if (download?.phase === 'complete') modelOperations.refreshCatalog() }, [download?.id, download?.phase, modelOperations])
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const [updateMessage, setUpdateMessage] = useState('')
  const [appUpdating, setAppUpdating] = useState(false)
  const [appUpdateResult, setAppUpdateResult] = useState('')
  const [autoUpdateProgress, setAutoUpdateProgress] = useState<{ stage: string; percent: number; version?: string } | null>(null)
  const [explorerOpen, setExplorerOpen] = useState(false)
  const projectToggleRef=useRef<HTMLButtonElement>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [showMemories, setShowMemories] = useState(false)
  const [showSources,setShowSources]=useState(false)
  const sourcesPresent=usePresence(showSources&&!askReq&&!confirmReq&&!showSettings&&!showPicker&&!showMemories)
  const memoriesPresent = usePresence(showMemories && !askReq && !confirmReq && !showSettings && !showPicker && !showSources)
  const explorerPresent = usePresence(explorerOpen)
  const pickerPresent = usePresence(showPicker && !askReq && !confirmReq)
  const settingsPresent = usePresence(showSettings && !askReq && !confirmReq)
  const [chats,setChats]=useState<Array<{path:string;hasHistory:boolean;messageCount:number}>>([])
  const [chatsLoading,setChatsLoading]=useState(false)
  const [chatsError,setChatsError]=useState(false)
  const [chatRevision,setChatRevision]=useState(0)
  const chatsObserved=useRef(false)
  const [settingsSection,setSettingsSection]=useState<SettingsSection>('general')
  useEffect(() => { if (confirmReq || askReq) { setShowSettings(false); setShowPicker(false); setShowSources(false); setShowMemories(false); } }, [confirmReq?.approvalId, askReq?.inputRequestId])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [selectedSource,setSelectedSource]=useState<SourceFile|null>(null)
  const [selectedMemory,setSelectedMemory]=useState<MemoryInspection|null>(null)
  const [projects, setProjects] = useState<ProjectState | null>(null)
  const [projectErrorCode, setProjectErrorCode] = useState<string | null>(null)
  const [projectActionPending, setProjectActionPending] = useState(false)
  const [projectPreviewRevision, setProjectPreviewRevision] = useState(0)
  const projectRequestRevision = useRef(0)
  const projectActionLocked = useRef(false)
  const rootDir = projects?.activePath || null
  const [selectedFileRoot, setSelectedFileRoot] = useState<string | null>(null)
  const [fileViewerOpen, setFileViewerOpen] = useState(false)
  const viewerOpen = general.showFiles && fileViewerOpen && !!(selectedFile||selectedSource||selectedMemory) && !!rootDir && sameProjectPath(selectedFileRoot, rootDir)
  const viewerPresent = usePresence(viewerOpen)
  const [appVersion, setAppVersion] = useState('')
  const [backendGitCapability, setBackendGitCapability] = useState<'UNAVAILABLE' | 'AVAILABLE_NOT_REPOSITORY' | 'AVAILABLE_REPOSITORY' | null>(null)
  const explorerRefreshKey = (view?.fileRevision || 0) + projectPreviewRevision
  const terminalRef = useRef<HTMLDivElement>(null)
  const followOutputRef = useRef(true)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [inputText, setInputText] = useState('')
  const [modelSelectionError, setModelSelectionError] = useState(false)
  const [pendingModel, setPendingModel] = useState<string | null>(null)
  const [embeddingSelectionPending,setEmbeddingSelectionPending]=useState(false)
  const embeddingSelectionLock=useRef(false)
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
  const chatTitle = fileBasename(view?.workspace || rootDir || '')
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
  // Host snapshots recreate the folder array even when no paths changed. Only real membership changes reload chats.
  const projectChatPaths=JSON.stringify((projects?.folders||[]).map(folder=>folder.path))
  const projectChatsAvailable=!!projects
  useEffect(()=>{
    if(!showSettings || settingsSection!=='chat' || !projectChatsAvailable || !status.ready || streaming || downloadBusy)return
    let active=true;setChatsLoading(!chatsObserved.current);setChatsError(false)
    void window.api.getProjectChats().then(result=>{
      if(!active)return
      if(!result.success || !Array.isArray(result.chats)){setChatsError(true);return}
      const next=result.chats.filter(chat=>typeof chat.path==='string' && typeof chat.hasHistory==='boolean' && Number.isInteger(chat.messageCount))
      chatsObserved.current=true
      setChats(previous=>previous.length===next.length && previous.every((chat,index)=>chat.path===next[index].path && chat.hasHistory===next[index].hasHistory && chat.messageCount===next[index].messageCount)?previous:next)
    }).catch(()=>{if(active)setChatsError(true)}).finally(()=>{if(active)setChatsLoading(false)})
    return()=>{active=false}
  },[showSettings,settingsSection,projectChatsAvailable,status.ready,streaming,downloadBusy,view?.sessionId,view?.workspace,projectChatPaths,chatRevision])
  const readiness = view?.readiness
  const readinessReason = readiness ? readiness.reason : (status.connected ? 'CHECKING' : 'BACKEND_DISCONNECTED')
  const installedModels = useMemo(() => readiness?.installedModels.map(model => model.name) || [], [readiness?.installedModels])
  const llmModels = useMemo(()=>readiness?.installedModels.filter(model=>model.kind==='llm').map(model=>model.name)||[],[readiness?.installedModels])
  const embeddingModels = useMemo(()=>readiness?.installedModels.filter(model=>model.kind==='embedding')||[],[readiness?.installedModels])
  const visibleModels = useMemo(() => llmModels.filter(model => !modelVisibility.hiddenModels.includes(model)), [llmModels,modelVisibility.hiddenModels])
  const promptModelReady = status.provider !== 'ollama' || modelVisibility.ready && visibleModels.includes(status.model)
  const loadingInstalledModels = readinessReason === 'CHECKING' && installedModels.length === 0
  const systemReady = !!readiness?.ready && status.connected && !pendingModel && !downloadBusy
  const responseDelayed = systemReady && view?.error?.code === 'OLLAMA_RESPONSE_TIMEOUT'
  const readinessOwnsError = responseDelayed || !systemReady && ['OLLAMA_CONNECTION_FAILED', 'OLLAMA_CONNECT_TIMEOUT', 'OLLAMA_MODEL_UNAVAILABLE'].includes(view?.error?.code || '')

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
  const clearProjectPreview=useCallback(()=>{
    setFileViewerOpen(false);setSelectedFile(null);setSelectedSource(null);setSelectedMemory(null);setSelectedFileRoot(null)
  },[])
  useEffect(clearProjectPreview, [rootDir, general.showFiles,view?.sessionId,view?.status.connected,clearProjectPreview])
  const managementOpen=showMemories||showSources||showSettings
  const proposalNotifications=useMemoryProposalNotifications(view,showMemories,managementOpen||showPicker||downloadBusy||projectActionPending||!!projects?.busy)
  const promptSources=usePromptSources(view,rootDir,downloadBusy||projectActionPending||!!projects?.busy||streaming||submitting||showPicker||!!askReq||!!confirmReq,
    ()=>{setProjectPreviewRevision(value=>value+1);if(general.showFiles)setExplorerOpen(true)})
  const managementWasOpen=useRef(managementOpen)
  useEffect(()=>{
    if(managementWasOpen.current&&!managementOpen){clearProjectPreview();setProjectPreviewRevision(revision=>revision+1)}
    managementWasOpen.current=managementOpen
  },[managementOpen,clearProjectPreview])
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

          modelOperations.backendReady()
          break

        case 'update_available':
          setUpdateAvailable(true)
          setUpdateMessage(msg.message || 'Update available')
          break

        case 'updating':
          setAppUpdating(true)
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
    if (!text.trim() || !systemReady || !promptModelReady || streaming || submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    setSubmitError(false)
    if(promptSources.uploading||!promptSources.selectionReady){submittingRef.current=false;setSubmitting(false);return}
    const attachmentRefs=promptSources.attachmentRefs
    try {
      const receipt = await window.api.applicationCommand('SubmitUserInput', { content: text, attachmentRefs })
      if (receipt.accepted) {
        if (general.autoSwitchView) setActiveView('history')
        promptSources.clear()
        setSentFeedback({ id: ++sendFeedbackRevision.current, text: inputRef.current?.value === text ? text : '' })
        setInputText(current => current === text ? '' : current)
      } else setSubmitError(true)
    } catch { setSubmitError(true) }
    finally { submittingRef.current = false; setSubmitting(false) }
  }, [promptSources,systemReady,promptModelReady,streaming,general.autoSwitchView])

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

    const binding = bindingFromEvent(e.nativeEvent, shortcuts.mac)
    if (binding && binding === shortcuts.bindings.newLine) {
      e.preventDefault()
      const field = e.currentTarget, start = field.selectionStart, end = field.selectionEnd
      setInputText(text => text.slice(0, start) + '\n' + text.slice(end))
      requestAnimationFrame(() => field.setSelectionRange(start + 1, start + 1))
      return
    }
    if (binding && binding === shortcuts.bindings.sendMessage) {
      e.preventDefault()
      if (e.repeat) return
      if (streaming) {
        // Stop current stream first; user can then send their message.
        handleStop()
        return
      }
      void sendMessage(inputText)
    }
  }, [inputText, sendMessage, streaming, handleStop, shortcuts.bindings, shortcuts.mac])

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

  const visibilitySelectionAttempt = useRef<string|null>(null)
  useEffect(() => {
    const hidden = status.provider === 'ollama' && modelVisibility.ready && (modelVisibility.hiddenModels.includes(status.model) || readiness?.installedModels.some(model=>model.name===status.model&&model.kind==='embedding'))
    if (!hidden) { visibilitySelectionAttempt.current = null; return }
    // Finish the pinned turn before changing its model. Retry only after the choices or session change.
    if (!visibleModels.length || !status.ready || modelVisibility.busy || downloadBusy || streaming || pendingModel ||
        projectActionPending || projects?.busy || view?.recovering || view?.activeTurnId || view?.activeGenerationId || askReq || confirmReq) return
    const attempt = JSON.stringify([view?.sessionId,view?.workspace,status.model,visibleModels])
    if (visibilitySelectionAttempt.current === attempt) return
    visibilitySelectionAttempt.current = attempt
    void handleModelSelect(visibleModels[0])
  }, [status.provider,status.model,status.ready,modelVisibility.ready,modelVisibility.hiddenModels,modelVisibility.busy,visibleModels,
      downloadBusy,streaming,pendingModel,projectActionPending,projects?.busy,view?.sessionId,view?.workspace,view?.recovering,
      view?.activeTurnId,view?.activeGenerationId,askReq,confirmReq,handleModelSelect])

  const handlePull = useCallback((model: string) => {
    if (downloadBusy || streaming || projectActionPending || pendingModel || !status.ready) return
    if (modelOperations.pull(model)) setShowPicker(false)
  }, [modelOperations,downloadBusy,streaming,projectActionPending,pendingModel,status.ready])

  const handleUpdateCatalog = useCallback(() => {
    modelOperations.sync()
  }, [modelOperations])

  const handleDelete = useCallback((model: string) => {
    modelOperations.delete(model)
  }, [modelOperations])

  const handleRecommend = useCallback(() => {
    modelOperations.recommend()
  }, [modelOperations])

  const handleClearHistory = useCallback(async (path:string) => {
    const result = await window.api.clearProjectChat(path)
    if(result.success)setChatRevision(revision=>revision+1)
    return result
  }, [])

  const handleAppUpdate = useCallback(() => {
    setAppUpdating(true)
    setAppUpdateResult('')
    window.api.sendToPython({ id: nextId(), type: 'do_update' })
  }, [])

  const openReadinessConfiguration = useCallback(() => {
    if (downloadBusy) return
    if (readiness?.requiredAction === 'SELECT_MODEL') {
      setShowSettings(false)

      refreshCatalog()
      setShowPicker(true)
    } else if (readiness?.requiredAction === 'CONFIGURE_PROVIDER') {
      setSettingsSection('connection'); setShowPicker(false); setShowSettings(true)
    }
  }, [downloadBusy,readiness?.requiredAction,refreshCatalog])

  const handleFileSelect = useCallback((path: string) => {
    if (!rootDir || !general.showFiles) return
    setSelectedFileRoot(rootDir)
    setSelectedFile(path)
    setSelectedSource(null);setSelectedMemory(null)
    setFileViewerOpen(true)
  }, [rootDir, general.showFiles])

  const handleSourceSelect=useCallback((source:SourceFile)=>{
    if(!rootDir||!general.showFiles||!sameProjectPath(source.projectPath,rootDir))return
    setSelectedFileRoot(rootDir);setSelectedFile(null);setSelectedMemory(null);setSelectedSource(source);setFileViewerOpen(true)
  },[rootDir,general.showFiles])
  const handleMemorySelect=useCallback((record:MemoryInspection)=>{
    if(!rootDir||!general.showFiles)return
    setSelectedFileRoot(rootDir);setSelectedFile(null);setSelectedSource(null);setSelectedMemory(record);setFileViewerOpen(true)
  },[rootDir,general.showFiles])

  const handleProjectAction = useCallback(async (action: ProjectAction, path?: string) => {
    if (downloadBusy || projectActionLocked.current || promptSources.uploading) return
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
    }, [downloadBusy,promptSources.uploading])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.keyCode === 229 || askReq || confirmReq) return
      const binding = bindingFromEvent(event, shortcuts.mac)
      if (!binding) return
      const action = (Object.keys(shortcuts.bindings) as ShortcutAction[]).find(id => shortcuts.bindings[id] === binding)
      if (!action || action === 'sendMessage' || action === 'newLine') return
      // Other dialogs and text inputs keep their own navigation and key behavior.
      if ((showPicker || showSettings || document.querySelector('[role="dialog"]')) && action !== 'settings') return
      event.preventDefault()
      if (event.repeat) return
      switch (action) {
        case 'settings':
          setShowSources(false); setShowMemories(false); setShowPicker(false); setSettingsSection('general'); setShowSettings(value => !value); break
        case 'projects': setExplorerOpen(value => !value); break
        case 'sources':
          if (status.ready) { setShowMemories(false); setShowPicker(false); setShowSettings(false); setShowSources(true) } break
        case 'memories':
          if (status.ready) { setShowSources(false); setShowPicker(false); setShowSettings(false); setShowMemories(true) } break
        case 'models':
          if (status.ready && !downloadBusy) { setShowSources(false); setShowMemories(false); refreshCatalog(); setShowPicker(true) } break
        case 'focusPrompt': inputRef.current?.focus(); break
        case 'toggleHistory': if (conversation?.hasConversation) setActiveView(value => value === 'home' ? 'history' : 'home'); break
        case 'showHome': setActiveView('home'); break
        case 'stopGeneration': if (streaming) handleStop(); break
        case 'closePreview': setFileViewerOpen(false); break
        case 'addProject':
          if (!downloadBusy && !projectActionPending && !streaming) void handleProjectAction('add'); break
        case 'attachFile':
          if(promptSources.canImport)void promptSources.acquire();break
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [shortcuts.bindings, shortcuts.mac, askReq, confirmReq, showPicker, showSettings, downloadBusy,
      refreshCatalog, conversation?.hasConversation, streaming, handleStop, projectActionPending, handleProjectAction, status.ready, promptSources])

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
        <button ref={projectToggleRef} className={`nova-nav-button ${explorerOpen ? 'active' : ''}`} aria-controls="nova-project-pane"
          title={shortcutTitle(t('projects'), 'projects')} aria-label={t('projects')} aria-expanded={explorerOpen}
          onClick={() => setExplorerOpen(v => !v)}><NovaIcon name="folder" size={28} /></button>
        <button className={'nova-nav-button '+(showSources?'active':'')} data-open-sources
          title={shortcutTitle(t('sources'),'sources')} aria-label={t('sources')} aria-haspopup="dialog"
          onClick={()=>{setShowMemories(false);setShowPicker(false);setShowSettings(false);setShowSources(true)}}><NovaIcon name="search" size={28}/></button>
        <button className={'nova-nav-button '+(showMemories?'active':'')} data-open-memories
          title={shortcutTitle(t('memoryRecords'),'memories')} aria-label={proposalNotifications.counts.window?`${t('memoryRecords')}: ${proposalNotifications.counts.window} ${t('memoriesUnreadProposals')}`:t('memoryRecords')} aria-haspopup="dialog"
          onClick={()=>{setShowSources(false);setShowPicker(false);setShowSettings(false);setShowMemories(true)}}>
          <NovaIcon name="memories" size={28}/>{proposalNotifications.counts.window>0&&<span className="nova-unread-badge" data-memory-notification="window" aria-hidden="true">{proposalNotifications.counts.window>99?'99+':proposalNotifications.counts.window}</span>}</button>
        <button className={`nova-nav-button ${showPicker ? 'active' : ''}`}
          title={downloadBusy ? t('modelDownloadBusy') : shortcutTitle(t('models'),'models')} aria-label={t('models')} aria-haspopup="dialog" disabled={downloadBusy}
          onClick={() => { setShowSources(false); setShowMemories(false); setShowSettings(false); refreshCatalog(); setShowPicker(true) }}>
          <NovaIcon name="brain" size={28} /></button>
        <div className="nova-rail-spacer" />
        <button className={`nova-nav-button ${showSettings ? 'active' : ''}`}
          title={shortcutTitle(t('settings'), 'settings')} aria-label={t('settings')} aria-haspopup="dialog"
          onClick={() => { setShowSources(false); setShowMemories(false); setShowPicker(false); setSettingsSection('general'); setShowSettings(true) }}>
          <NovaIcon name="settings" size={28} /></button>
      </nav>

      <div className="nova-workspace">
        <div className="nova-main">
        {explorerPresent && (
          <ProjectPane open={explorerOpen} onCollapse={()=>setExplorerOpen(false)} toggleRef={projectToggleRef}>
            <FileExplorer
              projects={projects}
              showFiles={general.showFiles}
              busy={downloadBusy || projectActionPending || promptSources.uploading || streaming || managementOpen || !!view?.approvals.length || !!view?.inputs.length}
              errorCode={projectErrorCode}
              onFileSelect={handleFileSelect}
              view={view}
              onSourceSelect={handleSourceSelect}
              selectedSourceIds={promptSources.selected.map(source=>source.id)}
              sourcePanelRevision={promptSources.panelRevision}
              onSourceChoose={promptSources.choose}
              onMemorySelect={handleMemorySelect}
              onPreviewClear={clearProjectPreview}
              onProjectAction={handleProjectAction}
              refreshKey={explorerRefreshKey}
            />
          </ProjectPane>
        )}

        <SourceDropTarget disabled={!promptSources.canImport||managementOpen} onFiles={files=>void promptSources.acquire(files)} label={activeView === 'home' ? t('home') : chatTitle}>
          {activeView === 'home' && <div className="nova-home-scene nova-view-enter" aria-hidden="true"><NovaMascot /></div>}
          <header className="nova-header">
            <div className="nova-history-title">{activeView === 'history' && <>
              <NovaIcon name="chat" strokeWidth={1.6} /><span>{chatTitle}</span>
            </>}</div>
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
            {(!downloadBusy || !status.connected) && <ReadinessNotice responseDelayed={responseDelayed} ready={systemReady} reason={readinessReason}
              requiredAction={readiness?.requiredAction || null} modelChanging={!!pendingModel}
              onConfigure={openReadinessConfiguration} onRecheck={() => recheckBackend(status.connected, window.api)}
              />}
            {localeError && !showSettings && <div className="confirm-bar" role="alert">{t(localeError)}</div>}
            {modelSelectionError && !showPicker && <div className="confirm-bar" role="alert">{t('modelChangeFailed')}</div>}
            {submitError && <div className="confirm-bar" role="alert">{t('submitFailed')}</div>}
            {view?.modelPreferenceError && <div className="confirm-bar" role="alert">{t('modelPreferenceSaveFailed')}</div>}
            {view?.error && !errorHasActivity && !readinessOwnsError && view.error.code !== 'MODEL_SELECTION_NOT_CONFIRMED'
              && !(modelSelectionError && ['MODEL_UNAVAILABLE', 'INVALID_MODEL', 'INVALID_MODEL_INFO',
                'PROVIDER_UNAVAILABLE', 'PROVIDER_VALIDATION_FAILED', 'CONFLICT_ACTIVE_TURN'].includes(view.error.code)) && <div className="confirm-bar" role="alert">
              <div><span>{t(applicationErrorKey(view.error.code))}</span>
                <details className="nova-activity-diagnostics"><summary>{t('diagnosticDetails')}</summary><pre>{view.error.code}{'\n'}{view.error.message}</pre></details>
              </div>
            </div>}
            {view?.gap && <div className="resume-bar" role="status">{t('eventGap')}</div>}

            {confirmReq && <div className="nova-permission-pending" role="status">
              <span>{t('activityAwaitingPermission')}</span>
              <button onClick={() => void reviewApproval()}>{t('reviewPermission')}</button>
            </div>}
            {confirmReq && approvalReviewError && <p className="nova-permission-error" role="alert">{t('reviewPermissionFailed')}</p>}
            {askReq && <QuestionModal key={`${view?.sessionId}:${askReq.inputRequestId}`} />}

            {promptSources.uploading&&<p className="nova-source-import-feedback" role="status">{t('sourcesWorking')}</p>}
            {promptSources.error&&<div className="nova-source-import-feedback" data-error role="alert">
              <p>{t(promptSources.error==='SOURCE_SELECTION_UNAVAILABLE'?'promptSourcesSelectionFailed':promptSources.error.includes('UNKNOWN')?'sourcesUnknown':'sourcesError')}</p>
              {promptSources.imported>0&&<p>{t('sourcesPartialImport')}: {promptSources.imported}</p>}
              <details><summary>{t('diagnosticDetails')}</summary><code>{promptSources.error}</code></details>
            </div>}
            <PromptSources sources={promptSources.selected} disabled={submitting} onRemove={promptSources.remove}/>
            <div className="nova-composer" data-submitting={submitting || undefined} data-sent={!!sentFeedback || undefined}>
              <button className="nova-attach-button" aria-label={t('attach')}
                title={view?.knowledge?.hostAcquisition ? t('attach') : t('attachmentsUnavailable')}
                disabled={!promptSources.canImport||managementOpen}
                onClick={() => void promptSources.acquire()}><NovaIcon name="plus" /></button>
              <div className="nova-prompt-field" data-sent={(!inputText && !!sentFeedback) || undefined}>
              <textarea ref={inputRef} className="input-field nova-input" value={inputText}
                onChange={e => setInputText(e.target.value)} onKeyDown={handleKeyDown}
                placeholder={!status.connected ? t('waitingBackend') : streaming ? t('stopHint') : t('promptPlaceholder')}
                aria-label={t('promptPlaceholder')} rows={1} />
              {sentFeedback?.text && !inputText && <div className="nova-prompt-sent" key={sentFeedback.id} aria-hidden="true">{sentFeedback.text}</div>}
              </div>
              <ModelSelector models={visibleModels} current={promptModelReady ? status.model : ''} onSelect={handleModelSelect}
                title={status.provider === 'ollama' ? t('installedOllamaModels') : t('ollamaModelSelectorUnavailable')}
                disabled={downloadBusy || streaming || !!pendingModel || !status.ready || status.provider !== 'ollama' || showSettings || showPicker || showMemories || showSources || !!askReq || !!confirmReq}
                placeholder={status.provider !== 'ollama' ? t('ollamaModelSelectorUnavailable')
                  : loadingInstalledModels ? t('loadingInstalledModels') : !visibleModels.length && installedModels.length ? t('llmNoEnabledModels') : installedModels.length ? t('selectModel') : t('noInstalledModels')} />
              <button className="nova-send-button" aria-label={streaming ? t('stop') : t('send')}
                title={streaming ? t('stop') : t('send')} disabled={streaming ? !status.ready : !systemReady || !promptModelReady || submitting || promptSources.uploading || !promptSources.selectionReady || !inputText.trim()}
                onClick={() => { if (streaming) handleStop(); else void sendMessage(inputText) }}>
                <NovaIcon name={streaming ? 'stop' : 'send'} /></button>
            </div>



          </div>
        </SourceDropTarget>

        {viewerPresent && rootDir && sameProjectPath(selectedFileRoot, rootDir) && (
          <div className="viewer-pane" data-exiting={!viewerOpen || undefined}
            inert={!viewerOpen} aria-hidden={!viewerOpen || undefined}>
            {selectedMemory?<MemoryItemViewer record={selectedMemory} onClose={()=>setFileViewerOpen(false)}/>
              :selectedSource?<SourceItemViewer key={`${rootDir}:${selectedSource.id}`} source={selectedSource} rootDir={rootDir} onClose={()=>setFileViewerOpen(false)}/>
              :selectedFile?<FileViewer key={`${rootDir}:${selectedFile}`} filePath={selectedFile} rootDir={rootDir}
                refreshKey={explorerRefreshKey} onClose={() => setFileViewerOpen(false)} />:null}
          </div>
        )}
        </div>
      </div>

      {pickerPresent && !showSettings && !showMemories && !showSources && (
        <ModelPicker open={showPicker && !askReq && !confirmReq} catalog={catalog} current={status.model}
          library={modelOperations.library} embeddingCurrent={view?.embedding?.selectedModel}
          embeddingModels={readiness?.installedModels.filter(model=>model.kind==='embedding').map(model=>model.name)}
          onSelectEmbedding={async model=>{
            if(!view?.embedding||downloadBusy||streaming||projectActionPending||pendingModel||!status.ready||embeddingSelectionLock.current)return
            embeddingSelectionLock.current=true;setEmbeddingSelectionPending(true)
            setModelSelectionError(false)
            try{
              const receipt=await window.api.applicationCommand('SetEmbeddingSettings',{modelId:model,
                requestedTokens:view.embedding.requestedTokens,enabledModels:[...new Set([...view.embedding.enabledModels,model])]})
              if(receipt.accepted)setShowPicker(false);else setModelSelectionError(true)
            }catch{setModelSelectionError(true)}finally{embeddingSelectionLock.current=false;setEmbeddingSelectionPending(false)}
          }}
          onSelect={handleModelSelect} onPull={handlePull} onDelete={handleDelete}
          onUpdate={handleUpdateCatalog} onClose={() => setShowPicker(false)} pulling={pulling}
          pullProgress={pullProgress} updating={updating} recommendations={recommendations}
           systemInfo={systemInfo} onRequestRecommend={handleRecommend} selectionError={modelSelectionError}
           selectionPending={!!pendingModel||embeddingSelectionPending} actionsDisabled={downloadBusy || streaming || projectActionPending || !status.ready}
           catalogLoading={modelState.catalogLoading} catalogError={modelState.catalogError}
           recommendError={modelState.recommendError}
           recommendationStatus={modelState.recommendationStatus}
           recommending={modelState.recommending} operationError={modelState.operationError}
           operationNotice={modelState.operationNotice} deleting={modelState.deleting}
           operationUnconfirmed={modelState.mutationUnconfirmed} onRefreshCatalog={refreshCatalog}
           installedModels={readiness?.observedAt && !['OLLAMA_UNAVAILABLE', 'READINESS_CHECK_FAILED', 'READINESS_STALE', 'CHECKING'].includes(readiness.reason || '') ? installedModels : undefined} />
      )}

      {sourcesPresent && !showSettings && !showPicker && !showMemories && <SourcesWindow key={`sources:${view?.sessionId}:${rootDir}`} view={view} open={showSources&&!askReq&&!confirmReq}
        locked={downloadBusy||projectActionPending||!!projects?.busy} projectRevision={JSON.stringify(projects?.folders.map(folder=>[folder.path,folder.name])||[])}
        onAcquire={promptSources.acquire} onImported={promptSources.selectImported} onClose={()=>setShowSources(false)}/>}

      {memoriesPresent && !showSettings && !showPicker && !showSources && <MemoryWindow view={view} open={showMemories&&!askReq&&!confirmReq}
        proposalNotifications={proposalNotifications}
        locked={downloadBusy||projectActionPending||!!projects?.busy} onClose={()=>setShowMemories(false)}/>}

      {settingsPresent && !showPicker && !showMemories && !showSources && (
        <SettingsPanel backendLocked={downloadBusy} open={showSettings && !askReq && !confirmReq} onClose={() => setShowSettings(false)} initialSection={settingsSection}
          chat={<ChatSettings disabled={downloadBusy || !status.ready || !!view?.recovering || streaming || !!view?.activeGenerationId || !!view?.approvals.length || !!view?.inputs.length || projectActionPending || !!projects?.busy}
            chats={visibleChats} loading={chatsLoading} error={chatsError} onClear={handleClearHistory}
            onOpen={path=>{setShowSettings(false);if(sameProjectPath(path,view?.workspace))setActiveView(conversation?.hasConversation?'history':'home');else void handleProjectAction('select',path)}} />}
          onSectionChange={setSettingsSection}
          connection={<LLMSettings view={view} models={llmModels} visibility={modelVisibility}
            active={showSettings&&settingsSection==='connection'} locked={downloadBusy}/>}
          embedding={<EmbeddingSettings view={view} models={embeddingModels} active={showSettings&&settingsSection==='embedding'} locked={downloadBusy}/> }
          projects={<ProjectsSettings projects={projects} busy={downloadBusy || projectActionPending || streaming || !!view?.activeGenerationId || !!view?.approvals.length || !!view?.inputs.length}
            errorCode={projectErrorCode} onAction={handleProjectAction}/>}
          web={<WebSettings key={`web:${view?.sessionId}:${rootDir}:${status.connected}`} view={view} />}
          memory={<MemorySettings key={`memory:${view?.sessionId}:${rootDir}:${status.connected}`} view={view} projects={projects} locked={downloadBusy||projectActionPending}/>}
          storage={<StorageSettings active={showSettings&&settingsSection==='storage'} projectRevision={JSON.stringify(projects?.folders.map(folder=>[folder.path,folder.name])||[])} locked={downloadBusy||projectActionPending||streaming||!!projects?.busy}/>}
          knowledge={<KnowledgeSettings key={`knowledge:${view?.sessionId}:${rootDir}:${status.connected}`} view={view} />}
          about={<AboutRuntime status={status}/>} />
      )}


    </div>
  )
}
