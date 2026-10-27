export type DesktopFontsResult = { success: true; fonts: string[] } | { success: false; error: { code: string; message: string } }
export function createDesktopFontService(): { get(): Promise<DesktopFontsResult> }
