export function createApprovalSurfaceController(options: {
  BrowserWindow: any; ipcMain: any; client: any; getParent: () => any;
  getLocale: () => string; preloadPath: string;
}): { sync(): void; invalidate(): void; reopenPending(): Promise<{ success: boolean }>; updateLocale(): void; dispose(): void }
