import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import {settingsEnglish,settingsSpanish} from './settings_locale'
import {desktopMessagesEnglish,desktopMessagesSpanish} from './desktop_messages_locale'
import {settingsServicesEnglish,settingsServicesSpanish} from './settings_services_locale'
import {knowledgeSettingsEnglish,knowledgeSettingsSpanish} from './knowledge_settings_locale'
import {memorySettingsEnglish,memorySettingsSpanish} from './memory_settings_locale'



export type DesktopLocale = 'es' | 'en'



const english = {
  ...settingsEnglish, ...desktopMessagesEnglish, ...settingsServicesEnglish, ...knowledgeSettingsEnglish, ...memorySettingsEnglish,
  modelInstalledCategory: 'Installed', modelGeneralCategory: 'General', modelSmallCategory: 'Small',
  modelJapaneseCategory: 'Japanese', modelMultilingualCategory: 'Multilingual', modelEmbeddingCategory: 'Embeddings',
  modelInventoryUnknown: 'Installed models unavailable', modelViewInstalled: 'View installed variants',
  modelSearchSubmit: 'Search library', modelCatalogFailed: 'The catalog could not be loaded. Try again.',
  modelSearchFailed: 'The model library search failed. Try another search when the connection is available.',
  modelRecommendFailed: 'Recommendations could not be loaded. Try again.', modelDownloadFailed: 'The download failed. Check Ollama and try again.',
  modelDeleteFailed: 'The model could not be deleted.', modelSyncFailed: 'The catalog could not be synchronized.',
  modelOperationUnconfirmed: 'The operation result could not be confirmed. Check the current state before repeating it.',
  modelDownloadComplete: 'Download completed. Select the model to use it.', modelDeleteComplete: 'Model deleted.',
  modelSyncComplete: 'Catalog synchronized.', modelDeleting: 'Deleting', modelRetry: 'Try again',
  modelLibraryNotice: 'Discover searches the Ollama library online. Results may include models that cannot run locally.',
  modelCatalogNotice: 'Catalog sizes and ratings are reference metadata. Local availability is checked with Ollama.',
  modelHardwareNotice: 'Recommendations use the detected hardware; they do not guarantee performance.',
  modelMetadataUnknown: 'Not reported', modelRatingSource: 'Catalog rating', modelFilterCount: 'models shown',
  modelDetails: 'Model details', modelClose: 'Close models', modelRefresh: 'Refresh installed models',
  modelDownloadAction: 'Download model', modelDeleteAction: 'Delete model', modelSelectAction: 'Use model',
  modelTabs: 'Model views', modelCategories: 'Model categories', modelSort: 'Sort results',
  modelCapabilities: 'Filter by capability', modelCloudOnly: 'Cloud only', modelDetectedHardware: 'Detected hardware',

  projectPreviousUnavailable: 'The previous folder is no longer available. Select another folder.',
  projectDefaultUnavailable: 'The default project could not be prepared. Add another folder to continue.',
  projectChangeNotConfirmed: 'The project change was not confirmed. Check the current folder before continuing.',
  projectDefaultRequired: 'The default project stays available in Nova.', projectLimitReached: 'The folder list is full. Remove a folder before adding another.',
  projectAdd: 'Add project', projectChange: 'Change project', projectRemove: 'Remove project',

  projectOpen: 'Open in File Explorer', projectOptions: 'Folder options', projectActive: 'Folder with access',

  projectDefault: 'Default project', projectSelect: 'Use this folder', projectLoading: 'Loading projects…',

  projectEmpty: 'No project folders are selected.', projectEmptyHint: 'Add a folder or use the default project.',

  projectUseDefault: 'Use default project', projectBusy: 'Wait for the current task to finish before changing projects.',

  projectOutsideRoot: 'This item is outside the active project.', projectStaleRoot: 'The project changed. Open this item again.',

  projectFileTooLarge: 'This file is too large to preview. The limit is 1 MB.', projectBinaryFile: 'Binary files cannot be previewed.',

  projectMissingFolder: 'The folder does not exist or cannot be accessed.', projectMissingFile: 'This file is no longer available.',

  projectUnavailable: 'Projects are unavailable. Check the backend connection.', projectSaveFailed: 'The project preference could not be saved.',

  projectOpenFailed: 'The folder could not be opened in File Explorer.', projectActionFailed: 'The project action could not be completed.',

  projectFolderLoading: 'Loading folder…', projectEmptyDirectory: 'Empty folder', projectMoreItems: 'Show more items',

  projectSymlink: 'Symbolic link — not expanded', projectListTruncated: 'The folder reached the display limit. Some items are not shown.',

  projectPreviewLoading: 'Loading preview…', projectPreviewTitle: 'File preview',

  projectRemoveHint: 'Removes the project from Nova and deletes its chat. The folder files remain on your computer.',

  modelGenerationFailed: 'The model could not generate a response. Check Ollama and available memory before trying again.',
  home: 'Home', projects: 'Projects', models: 'Models', settings: 'Settings', history: 'History',

  send: 'Send', stop: 'Stop', attach: 'Attach file', close: 'Close', selectModel: 'Select a model',

  copyMessage: 'Copy message', messageCopied: 'Copied', messageCopying: 'Copying…', messageCopyFailed: 'Could not copy',
  historyToday: 'today', conversationDate: 'Conversation date', historySavedDate: 'Saved on',
  activityReadHeading: 'Read', activityWriteHeading: 'Write', activityEditHeading: 'Edit',
  activityFetchHeading: 'Web fetch', activityTasksHeading: 'Tasks', activityQuestionHeading: 'Ask user',
  activityDelegateHeading: 'Delegation', activityMemoryHeading: 'Memory', activityMemoryReadHeading: 'Memory search',
  activityMemoryWriteHeading: 'Store memory', activityDocumentHeading: 'Document', activityDocumentReadHeading: 'Read document',
  activityDocumentSearchHeading: 'Search documents', activityNavigateHeading: 'Navigation', activityObserveHeading: 'Observation',
  activityClickHeading: 'Click', activityInputHeading: 'Text input', activityKeyHeading: 'Key press',
  activityBackHeading: 'Back', activityForwardHeading: 'Forward', activityReloadHeading: 'Reload',
  activityCloseBrowserHeading: 'Close browser', activityTakeoverHeading: 'Human intervention',
  activityUploadHeading: 'Upload', activityDownloadHeading: 'Download',
  activityProcessing: 'Processing', activityProcessingFor: 'Processing for', activityWorkedFor: 'Worked for',
  activityThoughtFor: 'Thought for', activityActions: 'Actions', activityWeb: 'Web activity', activityFilesAndCommands: 'Files and commands',
  activityCommands: 'Command activity', activityFiles: 'File activity', activityNeedsReview: 'Review result',
  promptPlaceholder: 'Work with Nova', thinking: 'Thinking',
  questionOpenFailed: 'The question dialog could not be opened. Try again.',
  messageSent: 'Message sent', questionHint: 'Answer so Nova can continue with your task.',
  questionPlaceholder: 'Write your answer…', questionSending: 'Sending…',
  questionAnswerSent: 'Answer sent. Waiting for Nova to continue…',
  questionAnswerFailed: 'Your answer could not be sent. Try again or stop the task.',

  backendConnected: 'Backend connected', backendConnecting: 'Connecting backend…',

  connectionOnlyNotice: 'Shows the connection to Nova; it does not verify model availability.',

  provider: 'Provider', version: 'Version', language: 'Interface language', spanish: 'Español', english: 'English',

  localeSaveFailed: 'The interface language could not be saved. Try again.',

  homeCaption: 'Your space with Nova.', composerHint: 'Enter to send · Shift+Enter for a new line',

  waitingBackend: 'Waiting for the backend…', stopHint: 'Stop generation', historyEmpty: 'Your conversation will appear here.',

  restoreConversation: 'Restore conversation', previousConversation: 'A previous conversation is available.',

  dismiss: 'Dismiss', clearConversation: 'Clear conversation', toolsAndSources: 'Tools and sources',

  sources: 'Sources', listSources: 'List sources', capacityStatus: 'Capacity and status', sourceUrl: 'Source URL',

  publicSnapshot: 'Public HTTP(S) snapshot', importUrl: 'Import URL to workspace',

  extractionUnavailable: 'Extraction is unavailable. These files cannot be used as context yet.',

  keepWorkspace: 'Keep in workspace', detail: 'Details', refreshFile: 'Refresh selected file', refreshUrl: 'Refresh URL',

  exportSource: 'Export', allowForwarding: 'Allow remote forwarding…', revokeForwarding: 'Revoke forwarding',

  deleteSource: 'Delete source', backendMetadata: 'Backend metadata', cancelImport: 'Cancel import',

  permissionRequired: 'Permission required', deny: 'Deny', allow: 'Allow', agentQuestion: 'Nova has a question',

  answerToAgent: 'Answer Nova', restartBackend: 'Restart backend', eventGap: 'Some session updates were interrupted. Unconfirmed results remain unknown.',

  localModel: 'Local model via Ollama', pulling: 'Downloading…', closePreview: 'Close preview',

  attachmentsUnavailable: 'Attachments are unavailable.', errorsUnavailable: 'This action is unavailable.',

  modelsTitle: 'Models', settingsTitle: 'Settings', closeDialog: 'Close dialog',

  installedOllamaModels: 'Installed Ollama models', noInstalledModels: 'No local models are installed.',

  loadingInstalledModels: 'Loading installed models…',

  ollamaModelSelectorUnavailable: 'Select Ollama to choose a local model',

  modelChangeFailed: 'The model could not be changed.',

  modelDownloadTitle: 'Downloading', modelDownloadUpdating: 'Updating models', modelDownloadFailedTitle: 'Download failed',
  modelDownloadLockHint: 'Some features will be available when the download finishes.',
  modelDownloadRefreshing: 'The download finished. Updating the installed model list and checking the connection…',
  modelDownloadWaiting: 'Waiting for download progress from Ollama. Controls remain paused until the operation finishes.',
  modelDownloadRefreshFailed: 'The download finished, but the installed model list could not be confirmed. Retry the update to continue.',
  modelDownloadRetryInventory: 'Retry update', modelDownloadFailureHint: 'The download could not be completed. Check Ollama before trying again.',
  modelDownloadBusy: 'Wait for the model download and model list update.', modelDownloadStatus: 'Downloading',
  systemReady: 'Ready', systemNotReady: 'Not ready', finishSetup: 'Finish setup',
  readinessCheckingTitle: 'Checking connection', readinessStatusTitle: 'Connection status',
  turnBusyAction: 'This action was not performed because a task is already running.',

  openConfiguration: 'Open settings', recheckReadiness: 'Check again', readinessChecking: 'Checking Ollama and the selected model…',

  readinessBackendDisconnected: 'Nova is not connected to its backend.',

  readinessOllamaUnavailable: 'Ollama is not available. Start Ollama and check again.',

  readinessNoModels: 'No local models are installed. Open Models to download one, then select it.',

  readinessSelectModel: 'Select an installed local model to start using Nova.',

  readinessModelMissing: 'The selected model is not installed. Select another model or download it.',

  readinessModelNotChat: 'The selected model does not support chat. Select a chat model.',

  readinessModelNoTools: 'The selected model does not support the tools Nova needs. Select a compatible model.',

  readinessModelValidation: 'The selected model could not be validated. Check again or select another model.',

  readinessProviderUnverified: 'This provider has not been verified for this Nova setup. Select Ollama to use local models.',

  readinessStale: 'The model state needs to be checked again before sending a message.',

  readinessCheckFailed: 'The system check could not finish. Check that Ollama is running and try again.',

  modelPreferenceSaveFailed: 'The model was selected, but its preference could not be saved for the next launch.',

  modelChanging: 'Changing model…', submitFailed: 'The message could not be sent. Your draft has been kept.',

  configureProvider: 'Select provider',

  unreadResponses: 'unread responses', historyStateSaveFailed: 'The history read state could not be saved. Your conversation is still available.',

  userMessage: 'Your message', novaMessage: 'Nova response', systemMessage: 'System message',

  responseInterrupted: 'Response interrupted', responseFailed: 'The response could not be completed',

  processingResults: 'Processing results', readingTool: 'Reading', writingTool: 'Writing', editingTool: 'Editing',

  searchingCodeTool: 'Searching code', searchingFilesTool: 'Searching files', runningTool: 'Running',

  askingTool: 'Asking', fetchingTool: 'Fetching', browserTool: 'Browser', searchingWebTool: 'Searching the web',

  toolResultReceived: 'Result received', toolRunning: 'Running', showOutput: 'Show output', collapseOutput: 'Collapse',

  activity: 'Activity', activityTool: 'Tool activity', delegatedTool: 'Delegated work',

  activityReadTool: 'File read', activityWriteTool: 'File write', activityEditTool: 'File edit',

  activityCodeSearchTool: 'Code search', activityFileSearchTool: 'File search', activityTerminalTool: 'Terminal',

  activityQuestionTool: 'Question', activityFetchTool: 'Web request', activityWebSearchTool: 'Web search',

  activityPending: 'Pending', activityCompleted: 'Execution confirmed', activityDenied: 'Permission denied',

  activityFailed: 'Could not execute', activityCancelled: 'Cancelled', activityTimedOut: 'Time limit reached',

  activityUnavailable: 'Tool unavailable', activityUnknown: 'The result could not be confirmed',

  activityAwaitingPermission: 'Waiting for permission', reviewPermission: 'Review permission',

  reviewPermissionFailed: 'The permission window could not be opened. Use Stop to cancel the task if you cannot continue.',

  activityPermissionExplanation: 'Review the request in the permission window to continue.',

  activityDeniedExplanation: 'Permission was denied. This request was not executed.',

  activityFailedExplanation: 'The tool reported a failure. Review its output for details.',

  activityCancelledExplanation: 'Execution was cancelled. Review the receipt before deciding what to do next.',

  activityTimedOutExplanation: 'Execution stopped after reaching its time limit.',

  activityUnavailableExplanation: 'This tool is unavailable in the current environment.',

  activityUnknownExplanation: 'The final effect is unknown. Verify the current state before repeating the action.',

  activityObservationLost: 'Connection to the operation was interrupted. Its final result has not been confirmed.',

  activityConnectionLost: 'The connection was interrupted. Pending operation results have not been confirmed.',

  activityNoOutput: 'No output has been received.', activityOutput: 'Output', activityStdout: 'Standard output', activityStderr: 'Error output',

  activityOutputTruncated: 'The visible output was shortened to fit the display limit.',

  diagnosticDetails: 'Diagnostic details', activityToolName: 'Tool', activityOperationId: 'Operation ID',

  activityToolCallId: 'Tool call ID', activityReceipt: 'Receipt', activityErrorCode: 'Error code', activityExitCode: 'Exit code',

  activityWorkingDirectory: 'Working directory', activityArguments: 'Arguments',

  activityHistorical: 'Tool details', activityUnverified: 'Execution unconfirmed',

  activityHistoricalExplanation: 'No typed execution receipt is available for this tool request. Its result cannot be confirmed.',

  actionFailed: 'The action could not be completed.',

  copyOutput: 'Copy output', copy: 'Copy', knowledgeCitations: 'Knowledge citations',

  structuralSources: 'Sources — structural references, not guaranteed entailment', revision: 'revision',

  sourceRevisionDetail: 'Source and revision details', invalidReferences: 'Invalid references',

  forYou: 'For you', catalog: 'Catalog', discover: 'Discover', installed: 'installed',

  sync: 'Sync', syncing: 'Syncing…', syncModels: 'Fetch the latest catalog from ollama.com',

  filterModels: 'Filter models…', loadingModels: 'Loading models…', all: 'All', noModelMatches: 'No models match.',

  searchModels: 'Search ollama.com…', searching: 'Searching…', noSearchResults: 'No results. Try another search.',

  popular: 'Popular', hot: 'Trending', newest: 'Newest', tools: 'Tools', code: 'Code', vision: 'Vision', reasoning: 'Reasoning',

  detectingSystem: 'Detecting system specifications…', ramUnknown: 'RAM unknown', systemUnknown: 'System specifications could not be detected.',

  active: 'Active', useModel: 'Use', download: 'Download', deleteModel: 'Delete', confirmDelete: 'Confirm?', cloud: 'Cloud',

  easeOfUse: 'Ease of use', downloads: 'downloads', downloading: 'Downloading',

  desktopApp: 'Desktop application', backend: 'Backend', update: 'Update', checking: 'Checking…',

  updatesNotConfigured: 'Desktop updates are not configured for Nova.',

  checkUpdates: 'Check for updates', upToDate: 'Up to date', installUpdate: 'Install update',

  updateAvailable: 'available', extracting: 'Extracting…', installingRestart: 'Installing… The app will restart.',

  preparing: 'Preparing…', installFailed: 'Installation failed.', updated: 'Updated.', updateFailed: 'Update failed.',

  updatingGit: 'Updating via git pull…', updateBackend: 'Update backend (git pull)',

  gitUnavailable: 'Git is not installed. Backend updates via git pull are unavailable.',

  gitNotRepository: 'The backend is not a Git checkout. Its Git update action is unavailable.',

  gitUpdateHint: 'Updates the Python backend from its Git repository. Restart after updating.',

  projectRetrieval: 'Project retrieval (RAG)', enableProjectRetrieval: 'Enable project retrieval', enable: 'Enable',

  retrievalUnavailable: 'Retrieval is unavailable; conversation remains available.', projectQuery: 'Project retrieval query',

  queryProject: 'Query project', keyboardShortcuts: 'Keyboard shortcuts', toggleExplorer: 'Toggle file explorer', newLine: 'New line',

  claudeAuthentication: 'Claude authentication', apiKey: 'API key', subscription: 'Subscription',

  authenticatedVia: 'Authenticated via', logout: 'Log out', apiKeyRequired: 'An API key is required.',

  apiKeyInvalid: 'Anthropic API keys must start with sk-ant-.', apiKeySaved: 'API key saved and validated.',

  apiKeySaveFailed: 'The API key could not be saved.', loggedIn: 'Logged in successfully.', loginFailed: 'Login failed.',

  enterApiKey: 'Enter your Anthropic API key. Get one from', validating: 'Validating…', saveValidate: 'Save and validate',

  subscriptionDescription: 'Log in with your Claude Pro or Max subscription. A browser window will open for authentication.',

  loggingIn: 'Logging in…', loginClaude: 'Log in with Claude', subscriptionRequired: 'An active Claude Pro or Max subscription is required.',

} as const



export type TranslationKey = keyof typeof english

const spanish: Record<TranslationKey, string> = {
  ...settingsSpanish, ...desktopMessagesSpanish, ...settingsServicesSpanish, ...knowledgeSettingsSpanish, ...memorySettingsSpanish,
  modelInstalledCategory: 'Instalados', modelGeneralCategory: 'General', modelSmallCategory: 'Pequeños',
  modelJapaneseCategory: 'Japonés', modelMultilingualCategory: 'Multilingüe', modelEmbeddingCategory: 'Embeddings',
  modelInventoryUnknown: 'Modelos instalados no disponibles', modelViewInstalled: 'Ver variantes instaladas',
  modelSearchSubmit: 'Buscar en la biblioteca', modelCatalogFailed: 'No se pudo cargar el catálogo. Vuelve a intentarlo.',
  modelSearchFailed: 'No se pudo consultar la biblioteca de modelos. Repite la búsqueda cuando haya conexión.',
  modelRecommendFailed: 'No se pudieron cargar las recomendaciones. Vuelve a intentarlo.', modelDownloadFailed: 'La descarga falló. Comprueba Ollama y vuelve a intentarlo.',
  modelDeleteFailed: 'No se pudo eliminar el modelo.', modelSyncFailed: 'No se pudo sincronizar el catálogo.',
  modelOperationUnconfirmed: 'No se pudo confirmar el resultado de la operación. Comprueba su estado antes de repetirla.',
  modelDownloadComplete: 'Descarga terminada. Selecciona el modelo para utilizarlo.', modelDeleteComplete: 'Modelo eliminado.',
  modelSyncComplete: 'Catálogo sincronizado.', modelDeleting: 'Eliminando', modelRetry: 'Volver a intentar',
  modelLibraryNotice: 'Descubrir consulta la biblioteca de Ollama en Internet. Puede incluir modelos que no se ejecutan localmente.',
  modelCatalogNotice: 'Los tamaños y valoraciones del catálogo son orientativos. La disponibilidad local se consulta en Ollama.',
  modelHardwareNotice: 'Las recomendaciones usan el hardware detectado; no garantizan rendimiento.',
  modelMetadataUnknown: 'No informado', modelRatingSource: 'Valoración del catálogo', modelFilterCount: 'modelos mostrados',
  modelDetails: 'Detalles del modelo', modelClose: 'Cerrar modelos', modelRefresh: 'Actualizar modelos instalados',
  modelDownloadAction: 'Descargar modelo', modelDeleteAction: 'Eliminar modelo', modelSelectAction: 'Usar modelo',
  modelTabs: 'Vistas de modelos', modelCategories: 'Categorías de modelos', modelSort: 'Ordenar resultados',
  modelCapabilities: 'Filtrar por capacidad', modelCloudOnly: 'Sólo en la nube', modelDetectedHardware: 'Hardware detectado',

  projectPreviousUnavailable: 'La carpeta anterior ya no está disponible. Selecciona otra carpeta.',
  projectDefaultUnavailable: 'No se pudo preparar el proyecto predeterminado. Añade otra carpeta para continuar.',
  projectChangeNotConfirmed: 'No se confirmó el cambio de proyecto. Comprueba la carpeta actual antes de continuar.',
  projectDefaultRequired: 'El proyecto predeterminado se conserva disponible en Nova.', projectLimitReached: 'La lista de carpetas está llena. Quita una antes de añadir otra.',
  projectAdd: 'Añadir proyecto', projectChange: 'Cambiar proyecto', projectRemove: 'Quitar proyecto',

  projectOpen: 'Abrir en el Explorador', projectOptions: 'Opciones de carpeta', projectActive: 'Carpeta con acceso',

  projectDefault: 'Proyecto predeterminado', projectSelect: 'Usar esta carpeta', projectLoading: 'Cargando proyectos…',

  projectEmpty: 'No hay carpetas de proyecto seleccionadas.', projectEmptyHint: 'Añade una carpeta o utiliza el proyecto predeterminado.',

  projectUseDefault: 'Usar proyecto predeterminado', projectBusy: 'Espera a que termine la tarea actual antes de cambiar de proyecto.',

  projectOutsideRoot: 'Este elemento está fuera del proyecto activo.', projectStaleRoot: 'El proyecto cambió. Abre este elemento de nuevo.',

  projectFileTooLarge: 'El archivo es demasiado grande para la vista previa. El límite es 1 MB.', projectBinaryFile: 'Los archivos binarios no tienen vista previa.',

  projectMissingFolder: 'La carpeta no existe o no es accesible.', projectMissingFile: 'Este archivo ya no está disponible.',

  projectUnavailable: 'Los proyectos no están disponibles. Comprueba la conexión con el backend.', projectSaveFailed: 'No se pudo guardar la preferencia del proyecto.',

  projectOpenFailed: 'No se pudo abrir la carpeta en el Explorador.', projectActionFailed: 'No se pudo completar la acción del proyecto.',

  projectFolderLoading: 'Cargando carpeta…', projectEmptyDirectory: 'Carpeta vacía', projectMoreItems: 'Mostrar más elementos',

  projectSymlink: 'Enlace simbólico: no se despliega', projectListTruncated: 'La carpeta alcanzó el límite de visualización. Algunos elementos no se muestran.',

  projectPreviewLoading: 'Cargando vista previa…', projectPreviewTitle: 'Vista previa del archivo',

  projectRemoveHint: 'Retira el proyecto de Nova y elimina su chat. Los archivos de la carpeta permanecen en el equipo.',

  modelGenerationFailed: 'El modelo no pudo generar una respuesta. Comprueba Ollama y la memoria disponible antes de volver a intentarlo.',
  home: 'Inicio', projects: 'Proyectos', models: 'Modelos', settings: 'Configuración', history: 'Historial',

  send: 'Enviar', stop: 'Detener', attach: 'Adjuntar archivo', close: 'Cerrar', selectModel: 'Seleccionar modelo',

  copyMessage: 'Copiar mensaje', messageCopied: 'Copiado', messageCopying: 'Copiando…', messageCopyFailed: 'No se pudo copiar',
  historyToday: 'hoy', conversationDate: 'Fecha de conversación', historySavedDate: 'Guardado el',
  activityReadHeading: 'Lectura', activityWriteHeading: 'Escritura', activityEditHeading: 'Edición',
  activityFetchHeading: 'Consulta web', activityTasksHeading: 'Tareas', activityQuestionHeading: 'Consulta al usuario',
  activityDelegateHeading: 'Delegación', activityMemoryHeading: 'Memoria', activityMemoryReadHeading: 'Consulta de memoria',
  activityMemoryWriteHeading: 'Guardar memoria', activityDocumentHeading: 'Documento', activityDocumentReadHeading: 'Lectura de documento',
  activityDocumentSearchHeading: 'Búsqueda en documentos', activityNavigateHeading: 'Navegación', activityObserveHeading: 'Observación',
  activityClickHeading: 'Clic', activityInputHeading: 'Entrada de texto', activityKeyHeading: 'Pulsación de tecla',
  activityBackHeading: 'Atrás', activityForwardHeading: 'Adelante', activityReloadHeading: 'Recarga',
  activityCloseBrowserHeading: 'Cierre del navegador', activityTakeoverHeading: 'Intervención humana',
  activityUploadHeading: 'Carga de archivo', activityDownloadHeading: 'Descarga de archivo',
  activityProcessing: 'Procesando', activityProcessingFor: 'Procesando desde hace', activityWorkedFor: 'Trabajó durante',
  activityThoughtFor: 'Pensó durante', activityActions: 'Acciones', activityWeb: 'Actividad web', activityFilesAndCommands: 'Archivos y comandos',
  activityCommands: 'Actividad con comandos', activityFiles: 'Actividad de archivos', activityNeedsReview: 'Revisar resultado',
  promptPlaceholder: 'Trabaja con Nova', thinking: 'Pensando',
  questionOpenFailed: 'No se pudo abrir el diálogo de consulta. Inténtalo de nuevo.',
  messageSent: 'Mensaje enviado', questionHint: 'Responde para que Nova pueda continuar con tu tarea.',
  questionPlaceholder: 'Escribe tu respuesta…', questionSending: 'Enviando…',
  questionAnswerSent: 'Respuesta enviada. Esperando a que Nova continúe…',
  questionAnswerFailed: 'No se pudo enviar tu respuesta. Inténtalo de nuevo o detén la tarea.',

  backendConnected: 'Backend conectado', backendConnecting: 'Conectando con el backend…',

  connectionOnlyNotice: 'Indica la conexión con Nova; no comprueba la disponibilidad del modelo.',

  provider: 'Proveedor', version: 'Versión', language: 'Idioma de la interfaz', spanish: 'Español', english: 'English',

  localeSaveFailed: 'No se pudo guardar el idioma de la interfaz. Inténtalo de nuevo.',

  homeCaption: 'Tu espacio con Nova.', composerHint: 'Intro para enviar · Mayús+Intro para una nueva línea',

  waitingBackend: 'Esperando al backend…', stopHint: 'Detener generación', historyEmpty: 'Tu conversación aparecerá aquí.',

  restoreConversation: 'Restaurar conversación', previousConversation: 'Hay una conversación anterior disponible.',

  dismiss: 'Descartar', clearConversation: 'Limpiar conversación', toolsAndSources: 'Herramientas y fuentes',

  sources: 'Fuentes', listSources: 'Listar fuentes', capacityStatus: 'Capacidad y estado', sourceUrl: 'URL de la fuente',

  publicSnapshot: 'Copia de una URL HTTP(S) pública', importUrl: 'Importar URL al proyecto',

  extractionUnavailable: 'La extracción no está disponible. Estos archivos aún no pueden usarse como contexto.',

  keepWorkspace: 'Conservar en el proyecto', detail: 'Detalles', refreshFile: 'Actualizar archivo seleccionado', refreshUrl: 'Actualizar URL',

  exportSource: 'Exportar', allowForwarding: 'Permitir envío remoto…', revokeForwarding: 'Revocar envío remoto',

  deleteSource: 'Eliminar fuente', backendMetadata: 'Metadatos del backend', cancelImport: 'Cancelar importación',

  permissionRequired: 'Se requiere permiso', deny: 'No permitir', allow: 'Permitir', agentQuestion: 'Nova tiene una pregunta',

  answerToAgent: 'Responder a Nova', restartBackend: 'Reiniciar backend', eventGap: 'Se interrumpieron algunas actualizaciones. Los resultados sin confirmar siguen siendo desconocidos.',

  localModel: 'Modelo local mediante Ollama', pulling: 'Descargando…', closePreview: 'Cerrar vista previa',

  attachmentsUnavailable: 'Los archivos adjuntos no están disponibles.', errorsUnavailable: 'Esta acción no está disponible.',

  modelsTitle: 'Modelos', settingsTitle: 'Configuración', closeDialog: 'Cerrar ventana',

  installedOllamaModels: 'Modelos instalados en Ollama', noInstalledModels: 'No hay modelos locales instalados.',

  loadingInstalledModels: 'Cargando modelos instalados…',

  ollamaModelSelectorUnavailable: 'Selecciona Ollama para elegir un modelo local',

  modelChangeFailed: 'No se pudo cambiar el modelo.',

  modelDownloadTitle: 'Descargando', modelDownloadUpdating: 'Actualizando modelos', modelDownloadFailedTitle: 'Descarga fallida',
  modelDownloadLockHint: 'Algunas características estarán disponibles al terminar la descarga.',
  modelDownloadRefreshing: 'La descarga terminó. Actualizando la lista de modelos instalados y comprobando la conexión…',
  modelDownloadWaiting: 'Esperando el progreso de descarga de Ollama. Los controles siguen en pausa hasta que termine la operación.',
  modelDownloadRefreshFailed: 'La descarga terminó, pero no se pudo confirmar la lista de modelos instalados. Reintenta la actualización para continuar.',
  modelDownloadRetryInventory: 'Reintentar actualización', modelDownloadFailureHint: 'No se pudo completar la descarga. Comprueba Ollama antes de intentarlo de nuevo.',
  modelDownloadBusy: 'Espera a que termine la descarga y se actualice la lista de modelos.', modelDownloadStatus: 'Descargando',
  systemReady: 'Listo', systemNotReady: 'No listo', finishSetup: 'Termina la configuración',
  readinessCheckingTitle: 'Comprobando conexión', readinessStatusTitle: 'Estado de conexión',
  turnBusyAction: 'No se realizó esta acción porque hay una tarea en curso.',

  openConfiguration: 'Abrir configuración', recheckReadiness: 'Volver a comprobar', readinessChecking: 'Comprobando Ollama y el modelo seleccionado…',

  readinessBackendDisconnected: 'Nova no está conectado con su backend.',

  readinessOllamaUnavailable: 'Ollama no está disponible. Abre Ollama y vuelve a comprobar.',

  readinessNoModels: 'No hay modelos locales instalados. Abre Modelos para descargar uno y después seleccionarlo.',

  readinessSelectModel: 'Selecciona un modelo local instalado para empezar a usar Nova.',

  readinessModelMissing: 'El modelo seleccionado no está instalado. Selecciona otro modelo o descárgalo.',

  readinessModelNotChat: 'El modelo seleccionado no admite chat. Selecciona un modelo de conversación.',

  readinessModelNoTools: 'El modelo seleccionado no admite las herramientas que Nova necesita. Selecciona un modelo compatible.',

  readinessModelValidation: 'No se pudo validar el modelo seleccionado. Vuelve a comprobar o selecciona otro modelo.',

  readinessProviderUnverified: 'Este proveedor no se ha verificado para esta configuración de Nova. Selecciona Ollama para usar modelos locales.',

  readinessStale: 'Es necesario comprobar de nuevo el estado del modelo antes de enviar un mensaje.',

  readinessCheckFailed: 'No se pudo completar la comprobación. Comprueba que Ollama esté activo e inténtalo de nuevo.',

  modelPreferenceSaveFailed: 'Se seleccionó el modelo, pero no se pudo guardar la preferencia para el próximo inicio.',

  modelChanging: 'Cambiando de modelo…', submitFailed: 'No se pudo enviar el mensaje. Se conservó tu borrador.',

  configureProvider: 'Seleccionar proveedor',

  unreadResponses: 'respuestas sin leer', historyStateSaveFailed: 'No se pudo guardar el estado de lectura del historial. Tu conversación sigue disponible.',

  userMessage: 'Tu mensaje', novaMessage: 'Respuesta de Nova', systemMessage: 'Mensaje del sistema',

  responseInterrupted: 'Respuesta interrumpida', responseFailed: 'No se pudo completar la respuesta',

  processingResults: 'Procesando resultados', readingTool: 'Leyendo', writingTool: 'Escribiendo', editingTool: 'Editando',

  searchingCodeTool: 'Buscando en el código', searchingFilesTool: 'Buscando archivos', runningTool: 'Ejecutando',

  askingTool: 'Consultando', fetchingTool: 'Consultando', browserTool: 'Navegador', searchingWebTool: 'Buscando en la web',

  toolResultReceived: 'Resultado recibido', toolRunning: 'En ejecución', showOutput: 'Mostrar resultado', collapseOutput: 'Contraer',

  activity: 'Actividad', activityTool: 'Actividad de herramienta', delegatedTool: 'Trabajo delegado',

  activityReadTool: 'Lectura de archivo', activityWriteTool: 'Escritura de archivo', activityEditTool: 'Edición de archivo',

  activityCodeSearchTool: 'Búsqueda en código', activityFileSearchTool: 'Búsqueda de archivos', activityTerminalTool: 'Terminal',

  activityQuestionTool: 'Consulta', activityFetchTool: 'Consulta web', activityWebSearchTool: 'Búsqueda web',

  activityPending: 'Pendiente', activityCompleted: 'Ejecución confirmada', activityDenied: 'Permiso denegado',

  activityFailed: 'No se pudo ejecutar', activityCancelled: 'Cancelada', activityTimedOut: 'Tiempo agotado',

  activityUnavailable: 'Herramienta no disponible', activityUnknown: 'No se pudo confirmar el resultado',

  activityAwaitingPermission: 'Esperando permiso', reviewPermission: 'Revisar permiso',

  reviewPermissionFailed: 'No se pudo abrir la ventana de permisos. Usa Detener para cancelar la tarea si no puedes continuar.',

  activityPermissionExplanation: 'Revisa la solicitud en la ventana de permisos para continuar.',

  activityDeniedExplanation: 'No se autorizó el permiso. Esta solicitud no se ejecutó.',

  activityFailedExplanation: 'La herramienta informó un fallo. Consulta su salida para ver los detalles.',

  activityCancelledExplanation: 'Se canceló la ejecución. Consulta el resultado antes de decidir cómo continuar.',

  activityTimedOutExplanation: 'La ejecución se detuvo al alcanzar el límite de tiempo.',

  activityUnavailableExplanation: 'Esta herramienta no está disponible en el entorno actual.',

  activityUnknownExplanation: 'Se desconoce el efecto final. Comprueba el estado actual antes de repetir la acción.',

  activityObservationLost: 'Se interrumpió la conexión con la operación. Su resultado final no se ha confirmado.',

  activityConnectionLost: 'Se interrumpió la conexión. No se han confirmado los resultados de las operaciones pendientes.',

  activityNoOutput: 'No se ha recibido salida.', activityOutput: 'Salida', activityStdout: 'Salida estándar', activityStderr: 'Salida de errores',

  activityOutputTruncated: 'La salida visible se recortó por el límite de visualización.',

  diagnosticDetails: 'Detalles de diagnóstico', activityToolName: 'Herramienta', activityOperationId: 'ID de operación',

  activityToolCallId: 'ID de llamada', activityReceipt: 'Resultado registrado', activityErrorCode: 'Código de error', activityExitCode: 'Código de salida',

  activityWorkingDirectory: 'Directorio de trabajo', activityArguments: 'Argumentos',

  activityHistorical: 'Detalles de herramienta', activityUnverified: 'Sin confirmación de ejecución',

  activityHistoricalExplanation: 'No hay un resultado de ejecución verificable para esta solicitud de herramienta. No se puede confirmar su resultado.',

  actionFailed: 'No se pudo completar la acción.',

  copyOutput: 'Copiar resultado', copy: 'Copiar', knowledgeCitations: 'Referencias de documentos',

  structuralSources: 'Fuentes — referencias estructurales, sin garantía de respaldo de cada afirmación', revision: 'revisión',

  sourceRevisionDetail: 'Detalles de fuente y revisión', invalidReferences: 'Referencias no válidas',

  forYou: 'Para ti', catalog: 'Catálogo', discover: 'Descubrir', installed: 'instalados',

  sync: 'Sincronizar', syncing: 'Sincronizando…', syncModels: 'Consultar el catálogo más reciente de ollama.com',

  filterModels: 'Filtrar modelos…', loadingModels: 'Cargando modelos…', all: 'Todos', noModelMatches: 'No hay modelos que coincidan.',

  searchModels: 'Buscar en ollama.com…', searching: 'Buscando…', noSearchResults: 'Sin resultados. Prueba otra búsqueda.',

  popular: 'Populares', hot: 'Tendencias', newest: 'Recientes', tools: 'Herramientas', code: 'Código', vision: 'Visión', reasoning: 'Razonamiento',

  detectingSystem: 'Detectando las características del sistema…', ramUnknown: 'RAM desconocida', systemUnknown: 'No se pudieron detectar las características del sistema.',

  active: 'Activo', useModel: 'Usar', download: 'Descargar', deleteModel: 'Eliminar', confirmDelete: '¿Confirmar?', cloud: 'Nube',

  easeOfUse: 'Facilidad de uso', downloads: 'descargas', downloading: 'Descargando',

  desktopApp: 'Aplicación de escritorio', backend: 'Backend', update: 'Actualización', checking: 'Comprobando…',

  updatesNotConfigured: 'Las actualizaciones de escritorio no están configuradas para Nova.',

  checkUpdates: 'Buscar actualizaciones', upToDate: 'Actualizado', installUpdate: 'Instalar actualización',

  updateAvailable: 'disponible', extracting: 'Extrayendo…', installingRestart: 'Instalando… La aplicación se reiniciará.',

  preparing: 'Preparando…', installFailed: 'La instalación falló.', updated: 'Actualizado.', updateFailed: 'La actualización falló.',

  updatingGit: 'Actualizando mediante git pull…', updateBackend: 'Actualizar backend (git pull)',

  gitUnavailable: 'Git no está instalado. La actualización del backend mediante git pull no está disponible.',

  gitNotRepository: 'El backend no es una copia de Git. Su actualización mediante Git no está disponible.',

  gitUpdateHint: 'Actualiza el backend Python desde su repositorio Git. Reinicia después de actualizar.',

  projectRetrieval: 'Consulta del proyecto (RAG)', enableProjectRetrieval: 'Habilitar consulta del proyecto', enable: 'Habilitar',

  retrievalUnavailable: 'La consulta no está disponible; la conversación sigue disponible.', projectQuery: 'Consulta del proyecto',

  queryProject: 'Consultar proyecto', keyboardShortcuts: 'Atajos de teclado', toggleExplorer: 'Mostrar u ocultar archivos', newLine: 'Nueva línea',

  claudeAuthentication: 'Autenticación de Claude', apiKey: 'Clave de API', subscription: 'Suscripción',

  authenticatedVia: 'Autenticado mediante', logout: 'Cerrar sesión', apiKeyRequired: 'Se requiere una clave de API.',

  apiKeyInvalid: 'Las claves de Anthropic deben comenzar por sk-ant-.', apiKeySaved: 'Clave de API guardada y validada.',

  apiKeySaveFailed: 'No se pudo guardar la clave de API.', loggedIn: 'Sesión iniciada correctamente.', loginFailed: 'No se pudo iniciar sesión.',

  enterApiKey: 'Introduce tu clave de API de Anthropic. Puedes obtenerla en', validating: 'Validando…', saveValidate: 'Guardar y validar',

  subscriptionDescription: 'Inicia sesión con tu suscripción Claude Pro o Max. Se abrirá una ventana del navegador para autenticarte.',

  loggingIn: 'Iniciando sesión…', loginClaude: 'Iniciar sesión con Claude', subscriptionRequired: 'Se requiere una suscripción activa de Claude Pro o Max.',

}



type LocaleResult = { success: true; preferences: { schemaVersion: 1; locale: DesktopLocale } }

  | { success: false; error: { code: string; message: string } }

type PreferencesHost = {

  getDesktopPreferences: () => Promise<{ schemaVersion: 1; locale: DesktopLocale }>

  setDesktopLocale: (locale: DesktopLocale) => Promise<LocaleResult>

}



export const translate = (locale: DesktopLocale, key: TranslationKey): string => (locale === 'en' ? english : spanish)[key]

const I18nContext = createContext({

  locale: 'es' as DesktopLocale,

  localeError: null as 'localeSaveFailed' | null,

  setLocale: async (_locale: DesktopLocale): Promise<boolean> => false,

  t: (key: TranslationKey): string => translate('es', key),

})



/** Presentation preferences only. Locale is never sent to the model or CLI. */

export function I18nProvider({ children }: { children: ReactNode }) {

  const [locale, setCurrentLocale] = useState<DesktopLocale>(() =>
    typeof window !== 'undefined' && window.api?.initialDesktopLocale === 'en' ? 'en' : 'es')

  const [localeError, setLocaleError] = useState<'localeSaveFailed' | null>(null)

  const requestedRevision = useRef(0)



  useEffect(() => {

    let alive = true

    const initialRevision = requestedRevision.current

    const host = typeof window === 'undefined' ? undefined : window.api as Partial<PreferencesHost> | undefined

    if (typeof host?.getDesktopPreferences === 'function') {

      void host.getDesktopPreferences().then(preferences => {

        if (alive && initialRevision === requestedRevision.current && preferences.schemaVersion === 1

            && (preferences.locale === 'es' || preferences.locale === 'en')) setCurrentLocale(preferences.locale)

      }).catch(() => { /* Keep the default; browser-only previews need no Electron host. */ })

    }

    return () => { alive = false }

  }, [])



  useEffect(() => { document.documentElement.lang = locale }, [locale])



  const setLocale = useCallback(async (next: DesktopLocale): Promise<boolean> => {

    if (next !== 'es' && next !== 'en') return false

    const revision = ++requestedRevision.current

    setLocaleError(null)

    const host = typeof window === 'undefined' ? undefined : window.api as Partial<PreferencesHost> | undefined

    if (typeof host?.setDesktopLocale !== 'function') {

      setCurrentLocale(next)

      return true

    }

    try {

      const result = await host.setDesktopLocale(next)

      if (!result.success || result.preferences.locale !== next) {

        if (revision === requestedRevision.current) setLocaleError('localeSaveFailed')

        return false

      }

      if (revision === requestedRevision.current) setCurrentLocale(next)

      return true

    } catch {

      if (revision === requestedRevision.current) setLocaleError('localeSaveFailed')

      return false

    }

  }, [])



  const t = useCallback((key: TranslationKey): string => translate(locale, key), [locale])

  return <I18nContext.Provider value={{ locale, localeError, setLocale, t }}>{children}</I18nContext.Provider>

}



export function useI18n() { return useContext(I18nContext) }

