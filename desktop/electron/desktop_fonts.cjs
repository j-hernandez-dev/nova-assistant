const { execFile } = require('node:child_process')
const path = require('node:path')

const failure = () => ({ success: false, error: { code: 'DESKTOP_FONTS_UNAVAILABLE', message: 'Installed fonts could not be read. System fonts remain available.' } })
const validFamily = family => typeof family === 'string' && family.trim().length > 0 && family.trim().length <= 128 && !/[\u0000-\u001f\u007f]/.test(family)
function fontFamilies(output, platform) {
  let families
  if (platform === 'linux') families = output.split(/\r?\n/).flatMap(line => line.split(','))
  else {
    const value = JSON.parse(output.replace(/^\uFEFF/, '').trim())
    families = typeof value === 'string' ? [value] : value
    if (!Array.isArray(families)) throw new Error('Invalid font inventory')
  }
  const unique = new Map()
  for (const item of families) {
    if (!validFamily(item)) continue
    const family = item.trim(), key = family.toLocaleLowerCase('en-US')
    if (!unique.has(key)) unique.set(key, family)
    if (unique.size > 4096) throw new Error('Font inventory is too large')
  }
  if (!unique.size) throw new Error('No font families were returned')
  return [...unique.values()].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
}

/** Read only: fixed OS font inventory commands, no renderer supplied arguments or file paths. */
function createDesktopFontService(options = {}) {
  const platform = options.platform || process.platform
  const execute = options.execFile || execFile
  let cached = null, pending = null
  function command() {
    if (platform === 'win32') return [path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe'),
      ['-NoLogo', '-NoProfile', '-NonInteractive', '-Command', "$ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); Add-Type -AssemblyName System.Drawing; $inventory = [System.Drawing.Text.InstalledFontCollection]::new(); try { @($inventory.Families | ForEach-Object { $_.Name }) | ConvertTo-Json -Compress } finally { $inventory.Dispose() }"]]
    if (platform === 'darwin') return ['/usr/bin/osascript', ['-l', 'JavaScript', '-e', "ObjC.import('AppKit'); JSON.stringify(ObjC.deepUnwrap($.NSFontManager.sharedFontManager.availableFontFamilies));"]]
    if (platform === 'linux') return ['/usr/bin/fc-list', ['--format=%{family}\n']]
    throw new Error('Unsupported font inventory platform')
  }
  return {
    async get() {
      if (cached) return { success: true, fonts: [...cached] }
      if (!pending) pending = new Promise(resolve => {
        try {
          const [file, args] = command()
          execute(file, args, { encoding: 'utf8', timeout: 15_000, maxBuffer: 4 * 1024 * 1024, windowsHide: true, shell: false }, (error, stdout) => {
            if (error) { resolve(failure()); return }
            try { cached = fontFamilies(stdout, platform); resolve({ success: true, fonts: [...cached] }) }
            catch { resolve(failure()) }
          })
        } catch { resolve(failure()) }
      }).finally(() => { pending = null })
      const result = await pending
      return result.success ? { success: true, fonts: [...result.fonts] } : result
    },
  }
}
module.exports = { createDesktopFontService, fontFamilies }
