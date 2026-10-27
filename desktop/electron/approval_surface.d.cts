export function createApprovalSurfaceController(options: {
  BrowserWindow: any; ipcMain: any; client: any; getParent: () => any;
  getLocale: () => string; preloadPath: string;
  getAppearance?: () => unknown; getSystemDark?: () => boolean; getPresentation?: () => ReturnType<typeof import('../shared/desktop_appearance').appearancePresentation>;
}): { sync(): void; invalidate(): void; reopenPending(): Promise<{ success: boolean }>; updateLocale(): void; updateAppearance(preferences?:unknown,systemDark?:boolean): void; dispose(): void }
