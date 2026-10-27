import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import electron, { startup } from 'vite-plugin-electron'
import renderer from 'vite-plugin-electron-renderer'
import { guardElectronDevExit, launchElectronDev, reloadOrLaunchElectronDev } from './dev/electron_exit.cjs'
import { shortcutDependencies } from './dev/shortcut_dependencies.cjs'

guardElectronDevExit(startup)

export default defineConfig({
  optimizeDeps: { include: ['three'] },
  build: { commonjsOptions: { include: [/node_modules/, /keyboard_shortcuts\.cjs$/] } },
  plugins: [
    shortcutDependencies(fileURLToPath(new URL('./shared/keyboard_shortcuts.cjs', import.meta.url))),
    react(),
    electron([
      {
        entry: 'electron/main.ts',
        onstart: () => launchElectronDev(startup),
        vite: {
          build: {
            outDir: 'dist-electron',
            commonjsOptions: { include: [/node_modules/, /keyboard_shortcuts\.cjs$/, /approval_(host|surface)\.cjs$/, /(confirmation|question)_surface\.cjs$/, /surface_appearance\.cjs$/, /(project_chats|model_usage)\.cjs$/, /desktop_(preferences|host_policy|model_preferences|model_visibility|fonts)\.cjs$/, /conversation_preferences\.cjs$/, /projects_host\.cjs$/, /console_pipes\.cjs$/, /python_runtime\.cjs$/, /chromium_cache\.cjs$/, /storage_host\.cjs$/, /memory_(control|files)\.cjs$/] },
          },
        },
      },
      {
        entry: 'electron/question_preload.ts',
        onstart({ reload }) { return reloadOrLaunchElectronDev(startup,reload) },
        vite: { build: { outDir: 'dist-electron' } },
      },
      {
        entry: 'electron/confirmation_preload.ts',
        onstart({ reload }) { return reloadOrLaunchElectronDev(startup,reload) },
        vite: { build: { outDir: 'dist-electron' } },
      },
      {
        entry: 'electron/approval_preload.ts',
        onstart({ reload }) { return reloadOrLaunchElectronDev(startup,reload) },
        vite: { build: { outDir: 'dist-electron' } },
      },
      {
        entry: 'electron/preload.ts',
        onstart({ reload }) {
          return reloadOrLaunchElectronDev(startup,reload)
        },
        vite: {
          build: {
            outDir: 'dist-electron',
          },
        },
      },
    ]),
    renderer(),
  ],
})
