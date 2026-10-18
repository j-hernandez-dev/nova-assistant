import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import electron from 'vite-plugin-electron'
import renderer from 'vite-plugin-electron-renderer'

export default defineConfig({
  plugins: [
    react(),
    electron([
      {
        entry: 'electron/main.ts',
        vite: {
          build: {
            outDir: 'dist-electron',
            commonjsOptions: { include: [/node_modules/, /approval_(host|surface)\.cjs$/, /(confirmation|question)_surface\.cjs$/, /project_chats\.cjs$/, /desktop_(preferences|host_policy|model_preferences)\.cjs$/, /conversation_preferences\.cjs$/, /projects_host\.cjs$/] },
          },
        },
      },
      {
        entry: 'electron/question_preload.ts',
        onstart({ reload }) { reload() },
        vite: { build: { outDir: 'dist-electron' } },
      },
      {
        entry: 'electron/confirmation_preload.ts',
        onstart({ reload }) { reload() },
        vite: { build: { outDir: 'dist-electron' } },
      },
      {
        entry: 'electron/approval_preload.ts',
        onstart({ reload }) { reload() },
        vite: { build: { outDir: 'dist-electron' } },
      },
      {
        entry: 'electron/preload.ts',
        onstart({ reload }) {
          reload()
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
