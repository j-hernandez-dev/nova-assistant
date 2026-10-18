export type MessageRole = 'user' | 'assistant' | 'tool' | 'system'

export type ToolCall = {
  name: string
  args: Record<string, unknown>
}

export type ToolResult = {
  name: string
  output: string
}

/** Owner-facing observation from Application, never execution authority. */
export type ToolActivity = {
  operationId: string; toolCallId: string; turnId: string; messageId: string | null
  name: string; arguments: Record<string, unknown>; cwd: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'denied' | 'cancelled' | 'outcome_unknown'
  operationStatus: string; effectState: 'none' | 'applied' | 'partial' | 'unknown'
  errorCode?: string | null; exitCode?: number | null
  output: string; stdout: string; stderr: string; outputSequence: number; outputTruncated: boolean
  startedAt?: string; completedAt?: string; observationLost?: boolean
}

/** Read-only timing/identity from Application's turn sidecar. Never tool authority. */
export type TurnObservation = {
  id: string; status: string; startedAt?: string; completedAt?: string
}

export type Message = {
  turn?: TurnObservation
  id: string
  role: MessageRole
  content: string
  sourceIndex?: number
  toolActivities?: ToolActivity[]
  errorCode?: string
  generationId?: string
  createdAt?: string
  savedAt?: string
  completedAt?: string
  deliveryStatus?: 'streaming' | 'completed' | 'cancelled' | 'failed'
  attachmentRefs?: import('../shared/application').AttachmentRef[]
  knowledgeCitations?:import('../shared/application').KnowledgeCitations
  toolCalls?: ToolCall[]
  toolResults?: ToolResult[]
  streaming?: boolean
  thinking?: boolean
  harnessEvents?: string[]
}

export type AppStatus = {
  model: string
  provider: string
  connected: boolean
  tools: string[]
  ready: boolean
}

export type FileEntry = {
  name: string
  isDirectory: boolean
  isSymlink: boolean
}

export type ProjectFolder = { path: string; name: string; isDefault: boolean }
export type ProjectState = {
  schemaVersion: 1; defaultPath: string; activePath: string | null
  folders: ProjectFolder[]; busy: boolean; error?: { code: string } | null
}
export type ProjectAction = 'add' | 'change' | 'select' | 'remove' | 'open'
export type ProjectActionResult = { success: boolean; canceled?: boolean; state: ProjectState; error?: { code: string } }
export type ListDirResult =
  | { success: true; root: string; path: string; entries: FileEntry[]; truncated: boolean; nextOffset: number | null; limitReached?: boolean }
  | { success: false; root?: string; path?: string; error: { code: string } }
export type ReadFileResult =
  | { success: true; root: string; path: string; content: string }
  | { success: false; root?: string; path?: string; size?: number; error: { code: string } }

export type ResumableInfo = {
  count: number
  saved_at?: string
  preview?: string
}

export type PythonMessage = {
  id?: number
  type: string
  content?: string
  name?: string
  args?: Record<string, unknown>
  output?: string
  data?: unknown
  event?: string
  resumable?: ResumableInfo | null
  messages?: Array<{ role: string; content: string }>
  confirm_id?: number
  input_request_id?: number
  question?: string
  command?: string
  model?: string
  tools?: string[]
  message?: string
  code?: string
  provider?: string
  has_claude?: boolean
  git_capability?: 'UNAVAILABLE' | 'AVAILABLE_NOT_REPOSITORY' | 'AVAILABLE_REPOSITORY'
  backend_git_capability?: 'UNAVAILABLE' | 'AVAILABLE_NOT_REPOSITORY' | 'AVAILABLE_REPOSITORY'
  has_updates?: boolean
  success?: boolean
  models?: unknown
  system?: unknown
}

declare global {
  interface Window {
    api: {
      getProjectChats: () => Promise<{success:boolean;chats?:Array<{path:string;hasHistory:boolean;messageCount:number;savedAt?:string|null}>;error?:{code:string}}>
      clearProjectChat: (path?:string) => Promise<{success:boolean;canceled?:boolean;error?:{code:string}}>
      initialDesktopLocale?: 'es' | 'en'
      initialDesktopAppearance?: import('../shared/desktop_appearance').AppearancePreferences
      copyMessage: (messageId: string) => Promise<{ success: boolean }>
      getDesktopPreferences: () => Promise<import('../electron/desktop_preferences.cjs').DesktopPreferences>
      setDesktopAppearance: (value: import('../shared/desktop_appearance').AppearancePreferences) => Promise<import('../electron/desktop_preferences.cjs').DesktopPreferencesResult>
      refreshReadiness: () => Promise<void>
      retryModelDownloadInventory: () => Promise<{success:boolean}>
      setHistoryVisible: (visible: boolean) => Promise<{ success: boolean }>
      reviewPendingApproval: () => Promise<{ success: boolean }>
      reviewPendingQuestion: () => Promise<{ success: boolean }>
      setDesktopLocale: (locale: 'es' | 'en') => Promise<
        { success: true; preferences: { schemaVersion: 1; locale: 'es' | 'en' } }
        | { success: false; error: { code: string; message: string } }
      >
      memoryCommand: (name: string, args: Record<string, unknown>, commandId?: string) => Promise<import('../shared/application').MemoryControlResult>
      knowledgePick: () => Promise<import('../shared/application').CommandReceipt>
      knowledgeRefresh:(sourceId:string)=>Promise<import('../shared/application').CommandReceipt>
      knowledgeExport:(sourceId:string)=>Promise<import('../shared/application').CommandReceipt>
      knowledgeCommand: (name:string,args:Record<string,unknown>,commandId?:string) => Promise<import('../shared/application').CommandReceipt>
      applicationCommand: (kind: string, payload: Record<string, unknown>, commandId?: string) => Promise<import('../shared/application').CommandReceipt>
      restartBackend: () => Promise<{ success: boolean; error?: string }>
      onSessionView: (cb: (view: import('../shared/application').DesktopSessionView) => void) => () => void
      signalReady: () => void
      sendToPython: (data: object) => void
      onPythonMessage: (cb: (msg: PythonMessage) => void) => () => void
      onPythonStderr: (cb: (text: string) => void) => () => void
      onPythonExit: (cb: (code: number | null) => void) => () => void
      getPythonStatus: () => Promise<{ running: boolean }>
      getProjects: () => Promise<ProjectState>
      onProjectsChanged: (callback: (state: ProjectState) => void) => () => void
      projectAction: (action: ProjectAction, path?: string) => Promise<ProjectActionResult>
      listDir: (dirPath: string, offset?: number) => Promise<ListDirResult>
      readFile: (filePath: string) => Promise<ReadFileResult>
      openDirectoryDialog: () => Promise<Electron.OpenDialogReturnValue>
      getHomeDir: () => Promise<string>
      hasClaudeAccess: () => Promise<boolean>
      getAppVersion: () => Promise<string>
      checkAppUpdate: () => Promise<{
        available: boolean
        version: string
        notes?: string
        downloadUrl?: string
        zipUrl?: string
        releaseUrl?: string
        error?: string
      }>
      installAppUpdate: (zipUrl: string) => Promise<{ success: boolean; error?: string }>
      onUpdateProgress: (cb: (progress: { stage: string; percent: number; version?: string }) => void) => () => void
      onAutoUpdateStart: (cb: (info: { version: string }) => void) => () => void
      openExternalUrl: (url: string) => Promise<void>
      getClaudeAuth: () => Promise<{
        method: string | null
        keyHint: string | null
        authenticated: boolean
      }>
      saveClaudeKey: (key: string) => Promise<{
        success: boolean
        error?: string
        keyHint?: string
      }>
      deleteClaudeAuth: () => Promise<{ success: boolean }>
      startClaudeOAuth: () => Promise<{
        success: boolean
        error?: string
      }>
    }
  }
}
