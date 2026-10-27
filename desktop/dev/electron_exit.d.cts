import type { ChildProcess } from 'node:child_process'
export function launchElectronDev(startup: typeof import('vite-plugin-electron').startup): Promise<void>
export function reloadOrLaunchElectronDev(startup: typeof import('vite-plugin-electron').startup,reload:()=>void): void|Promise<void>
export function guardElectronDevExit(startup: { exit: () => Promise<void> }, host?: {
  electronApp?: Pick<ChildProcess, 'exitCode' | 'signalCode'>
}): void
