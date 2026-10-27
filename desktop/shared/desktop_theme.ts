/** Presentation tokens shared by the renderer, startup document and native dialogs. */
export const themeIds = ['nova', 'synthwave84', 'matrix', 'box'] as const
export type ThemeId = typeof themeIds[number]
export type ColorScheme = 'system' | 'light' | 'dark'
export type ThemeMode = 'light' | 'dark'
export const SYSTEM_INTERFACE_FONT = 'system-ui, sans-serif'
export const SYSTEM_CODE_FONT = 'ui-monospace, monospace'

export interface ThemePalette {
  readonly id: ThemeId
  readonly mode: ThemeMode
  readonly colors: Readonly<Record<string, string>>
}

type PaletteSeed = {
  bg: string; panel: string; raised: string; input: string; hover: string
  text: string; dim: string; muted: string; border: string; accent: string
  green: string; red: string; purple: string; cyan: string; orange: string
  chrome: string; code: string; assistant: string; user: string
}

function palette(id: ThemeId, mode: ThemeMode, seed: PaletteSeed): ThemePalette {
  const light = mode === 'light'
  return Object.freeze({ id, mode, colors: Object.freeze({
    '--bg': seed.bg, '--bg-alt': seed.panel, '--bg-hover': seed.hover,
    '--bg-input': seed.input, '--panel': seed.panel, '--panel-raised': seed.raised,
    '--text': seed.text, '--text-dim': seed.dim, '--text-muted': seed.muted,
    '--text-dimmer': seed.muted, '--border': seed.border, '--accent': seed.accent,
    '--green': seed.green, '--yellow': seed.orange, '--red': seed.red,
    '--purple': seed.purple, '--cyan': seed.cyan, '--orange': seed.orange,
    '--code-bg': seed.code, '--bubble-assistant': seed.assistant, '--bubble-user': seed.user,
    '--nova-titlebar-bg': seed.chrome, '--nova-titlebar-text': seed.text,
    '--nova-frame-border': seed.border, '--nova-shadow': light ? '#302c38' : '#000000',
    '--nova-overlay': light ? '#5b5866' : '#000000',
    '--nova-emblem-bright': light ? '#15161b' : '#ffffff',
    '--nova-emblem-mid': light ? '#30333b' : '#f5f6f9',
    '--nova-emblem-shade': light ? '#686b75' : '#b5bac4',
    '--nova-emblem-glow': light ? '#31343f' : '#e5efff',
    '--nova-orbit-strong': id === 'nova' && !light ? '#ffc523' : seed.accent,
    '--nova-orbit-light': id === 'nova' && !light ? '#ffe174' : id === 'synthwave84' ? seed.cyan : seed.orange,
    '--nova-orbit-mid': id === 'nova' && !light ? '#ee9e00' : seed.accent,
    '--nova-orbit-dim': id === 'nova' && !light ? '#b77100' : seed.orange,
    '--nova-accent-foreground': light ? '#ffffff' : seed.bg,
  }) })
}

/** Original Nova dark remains the baseline; each theme has its own light palette. */
export const themePalettes: Readonly<Record<ThemeMode, Readonly<Record<ThemeId, ThemePalette>>>> = Object.freeze({
  dark: Object.freeze({
    nova: palette('nova', 'dark', {
      bg:'#090c12', panel:'#13171f', raised:'#1b1f28', input:'#10131b', hover:'#20232c',
      text:'#eef0f6', dim:'#b4bac8', muted:'#8f96a7', border:'#2b2f39', accent:'#ffc347',
      green:'#65cc82', red:'#f5897d', purple:'#bc8cff', cyan:'#56d4dd', orange:'#dba345',
      chrome:'#0a0a0a', code:'#0d1118', assistant:'#191e29', user:'#1f2531',
    }),
    synthwave84: palette('synthwave84', 'dark', {
      bg:'#211b30', panel:'#292239', raised:'#342b46', input:'#221c30', hover:'#3a2e50',
      text:'#f2e9ff', dim:'#cfc0e5', muted:'#a69abf', border:'#493b60', accent:'#ff7edb',
      green:'#72f1b8', red:'#ff8b8b', purple:'#c4a3ff', cyan:'#75e5f2', orange:'#f7c882',
      chrome:'#191422', code:'#241d33', assistant:'#2b243c', user:'#372b49',
    }),
    matrix: palette('matrix', 'dark', {
      bg:'#080e0b', panel:'#101b15', raised:'#17271d', input:'#0b140f', hover:'#203728',
      text:'#dcefe1', dim:'#a5c5af', muted:'#7f9f89', border:'#294633', accent:'#6de398',
      green:'#80e8a4', red:'#f19588', purple:'#b4bdeb', cyan:'#73d8c9', orange:'#cfcd78',
      chrome:'#070c09', code:'#09140e', assistant:'#14231a', user:'#1b3023',
    }),
    box: palette('box', 'dark', {
      bg:'#111111', panel:'#1b1b1b', raised:'#242424', input:'#161616', hover:'#303030',
      text:'#eeeeee', dim:'#bebebe', muted:'#969696', border:'#363636', accent:'#e5e5e5',
      green:'#94cba0', red:'#e49a94', purple:'#bfb1d5', cyan:'#9fc6d5', orange:'#d4bd91',
      chrome:'#202020', code:'#202020', assistant:'#191919', user:'#292929',
    }),
  }),
  light: Object.freeze({
    nova: palette('nova', 'light', {
      bg:'#fcfaf6', panel:'#f5f2eb', raised:'#ffffff', input:'#fffdfa', hover:'#eee8dc',
      text:'#292823', dim:'#5d5a52', muted:'#767167', border:'#d9d3c7', accent:'#8a5b0b',
      green:'#297744', red:'#b53e38', purple:'#7953a6', cyan:'#157782', orange:'#9a6422',
      chrome:'#eeeae2', code:'#f1eee7', assistant:'#f5f2eb', user:'#eae4d8',
    }),
    // The official SynthWave '84 extension contributes only a dark theme. This
    // light adaptation retains its lavender, pink and cyan family with readable ink.
    synthwave84: palette('synthwave84', 'light', {
      bg:'#fbf8ff', panel:'#f0eaf7', raised:'#ffffff', input:'#fffcff', hover:'#e9dff2',
      text:'#32263e', dim:'#655370', muted:'#7d6d89', border:'#d9cce4', accent:'#a02d80',
      green:'#267958', red:'#b53e54', purple:'#7752a3', cyan:'#147b90', orange:'#99652b',
      chrome:'#e8def1', code:'#f0eaf6', assistant:'#f3edf9', user:'#eaddf2',
    }),
    matrix: palette('matrix', 'light', {
      bg:'#f7fbf7', panel:'#eaf2eb', raised:'#ffffff', input:'#fbfffb', hover:'#dfece1',
      text:'#20392a', dim:'#4c6754', muted:'#6c7f70', border:'#cadbce', accent:'#247343',
      green:'#247343', red:'#af433b', purple:'#6a5790', cyan:'#217b75', orange:'#8b6d28',
      chrome:'#e0ece2', code:'#eaf2ec', assistant:'#edf5ef', user:'#dcebe0',
    }),
    box: palette('box', 'light', {
      bg:'#ffffff', panel:'#f6f6f6', raised:'#ffffff', input:'#fdfdfd', hover:'#eaeaea',
      text:'#292929', dim:'#575757', muted:'#757575', border:'#dedede', accent:'#3b3b3b',
      green:'#347848', red:'#ad4540', purple:'#785a99', cyan:'#287c91', orange:'#8a682c',
      chrome:'#f2f2f2', code:'#f4f4f4', assistant:'#fafafa', user:'#ededed',
    }),
  }),
})

export function resolveTheme(preferences: {
  colorScheme: ColorScheme; lightTheme: ThemeId; darkTheme: ThemeId
}, systemDark: boolean): ThemePalette {
  const mode = preferences.colorScheme === 'system' ? (systemDark ? 'dark' : 'light') : preferences.colorScheme
  const id = mode === 'dark' ? preferences.darkTheme : preferences.lightTheme
  return themePalettes[mode][id]
}
