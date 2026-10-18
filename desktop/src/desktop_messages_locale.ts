export const desktopMessagesEnglish = {
  desktopProvider: 'Model provider', desktopProviderSwitch: 'Switch model provider',
  desktopProviderLocal: 'Local model', desktopProviderAnthropic: 'Anthropic API',
  desktopProviderLoginRequired: 'Login required', desktopProviderLogin: 'Log in',
  desktopAuthInvalidKey: 'The API key is invalid.',
  desktopAuthNetwork: 'The authentication service could not be reached. Check the connection.',
  desktopAuthTimeout: 'Authentication timed out. Try again.',
  desktopAuthFailed: 'Authentication could not be completed. Try again.',
  desktopAuthLoadFailed: 'The saved authentication state could not be read.',
  desktopAuthSaveFailed: 'The API key could not be saved.',
  desktopAuthLogoutFailed: 'The authentication data could not be removed.',
  desktopAuthExternalFailed: 'The link could not be opened in your browser.',
}

export const desktopMessagesSpanish: Record<keyof typeof desktopMessagesEnglish, string> = {
  desktopProvider: 'Proveedor del modelo', desktopProviderSwitch: 'Cambiar proveedor del modelo',
  desktopProviderLocal: 'Modelo local', desktopProviderAnthropic: 'API de Anthropic',
  desktopProviderLoginRequired: 'Se requiere iniciar sesión', desktopProviderLogin: 'Iniciar sesión',
  desktopAuthInvalidKey: 'La clave de API no es válida.',
  desktopAuthNetwork: 'No se pudo contactar con el servicio de autenticación. Comprueba la conexión.',
  desktopAuthTimeout: 'Se agotó el tiempo de autenticación. Inténtalo de nuevo.',
  desktopAuthFailed: 'No se pudo completar la autenticación. Inténtalo de nuevo.',
  desktopAuthLoadFailed: 'No se pudo leer el estado de autenticación guardado.',
  desktopAuthSaveFailed: 'No se pudo guardar la clave de API.',
  desktopAuthLogoutFailed: 'No se pudieron eliminar los datos de autenticación.',
  desktopAuthExternalFailed: 'No se pudo abrir el enlace en tu navegador.',
}

export type DesktopMessageKey = keyof typeof desktopMessagesEnglish

// Only known host codes are mapped. Unrecognized provider/exception payloads
// never become UI text (and may contain sensitive details).
export function desktopAuthErrorKey(code: unknown, fallback: DesktopMessageKey = 'desktopAuthFailed'): DesktopMessageKey {
  switch (code) {
    case 'AUTH_INVALID_KEY': case 'Invalid API key.': return 'desktopAuthInvalidKey'
    case 'AUTH_NETWORK_FAILED': case 'Could not reach Anthropic API.': case 'Could not reach auth server.': return 'desktopAuthNetwork'
    case 'AUTH_TIMEOUT': case 'Request timed out.': case 'Auth request timed out.': case 'Login timed out. Please try again.': return 'desktopAuthTimeout'
    case 'AUTH_SAVE_FAILED': return 'desktopAuthSaveFailed'
    case 'AUTH_DELETE_FAILED': return 'desktopAuthLogoutFailed'
    default: return fallback
  }
}
