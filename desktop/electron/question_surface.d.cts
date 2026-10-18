export function createQuestionSurface(options: {
  BrowserWindow: any; ipcMain: any; client: any; getParent: () => any;
  getLocale: () => string; preloadPath: string; canOpen?: () => boolean
}): { sync(): void; invalidate(): void; reopenPending(): Promise<{ success: boolean }>; updateLocale(): void; dispose(): void }
