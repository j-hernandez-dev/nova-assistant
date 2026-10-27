import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { I18nProvider } from './i18n'
import { ShortcutsProvider } from './keyboard_shortcuts'
import { AppearanceProvider } from './appearance'
import './styles.css'
import './themes.css'
import './window_surfaces.css'
import { installStartupScreen } from '../shared/startup_screen'

// Browser previews use the same presentation; Electron installs it earlier in preload.
if (!document.getElementById('nova-startup')?.hasAttribute('data-startup-managed')) {
  const dispose = installStartupScreen(document, window.api?.initialDesktopLocale === 'en' ? 'en' : 'es', window.api?.initialDesktopAppearance, undefined, window.api?.initialDesktopGeneral?.transitionsEnabled, window.api?.initialDesktopSystemDark)
  window.addEventListener('unload', dispose, { once: true })
}

function renderApp() { ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider><ShortcutsProvider><AppearanceProvider><App /></AppearanceProvider></ShortcutsProvider></I18nProvider>
  </React.StrictMode>,
) }
if (document.getElementById('root')) renderApp()
else document.addEventListener('DOMContentLoaded', renderApp, { once: true })
