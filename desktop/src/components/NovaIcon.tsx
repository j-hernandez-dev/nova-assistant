import type { SVGProps } from 'react'

export type NovaIconName =
  | 'home' | 'folder' | 'brain' | 'sparkle' | 'settings' | 'history' | 'chat' | 'memories' | 'database'
  | 'send' | 'stop' | 'plus' | 'close' | 'chevron' | 'back'
  | 'terminal' | 'files' | 'file-read' | 'file-write' | 'file-edit' | 'search' | 'globe' | 'link'
  | 'browser' | 'pointer' | 'keyboard' | 'upload' | 'download' | 'refresh' | 'sync' | 'forward'
  | 'hand' | 'checklist' | 'agents' | 'tool' | 'workflow' | 'help' | 'eye' | 'copy' | 'check'

type Props = Omit<SVGProps<SVGSVGElement>, 'name'> & {
  name: NovaIconName
  size?: number
}

/** Shared line icons. Their containing control supplies the accessible name. */
export function NovaIcon({ name, size = 24, ...props }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.65" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" focusable="false" data-icon={name} {...props}>
      {name === 'home' && <>
        <path d="M8.5 4.4C9.8 1 14.3 1 15.5 4.4l1.3 3.7M19.6 8.5c3.4 1.3 3.4 5.8 0 7l-3.7 1.3M15.5 19.6c-1.3 3.4-5.8 3.4-7 0l-1.3-3.7M4.4 15.5c-3.4-1.3-3.4-5.8 0-7l3.7-1.3" />
        <path d="m8.6 8.6 6.8 6.8m0-6.8-6.8 6.8" />
      </>}
      {name === 'folder' && <>
        <path d="M3 6.5a2 2 0 0 1 2-2h4l2 2H19a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
        <path d="M3 10h18" />
      </>}
      {name === 'brain' && <>
        <path d="M12 5.5a3 3 0 0 0-5.8-1A3.5 3.5 0 0 0 3.6 10a3.5 3.5 0 0 0 .3 6.3A3.5 3.5 0 0 0 7 20a3 3 0 0 0 5-2.2Z" />
        <path d="M12 5.5a3 3 0 0 1 5.8-1 3.5 3.5 0 0 1 2.6 5.5 3.5 3.5 0 0 1-.3 6.3A3.5 3.5 0 0 1 17 20a3 3 0 0 1-5-2.2M7 5v3m-2 4h3v3m-1 5v-2m10-13v3m2 4h-3v3m1 5v-2M8 8h4m0 5h4" />
      </>}
      {name === 'settings' && <>
        <path d="m9.6 3-.5 2a7.3 7.3 0 0 0-1.7 1L5.5 5.4 3.1 9.6l1.4 1.5a7.5 7.5 0 0 0 0 1.9l-1.4 1.4 2.4 4.2 1.9-.6a7.3 7.3 0 0 0 1.7 1l.5 2h4.8l.5-2a7.3 7.3 0 0 0 1.7-1l1.9.6 2.4-4.2-1.4-1.5a7.5 7.5 0 0 0 0-1.9l1.4-1.4-2.4-4.2-1.9.6a7.3 7.3 0 0 0-1.7-1l-.5-2Z" />
        <circle cx="12" cy="12" r="3" />
      </>}
      {name === 'chat' && <path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 3V6a2 2 0 0 1 2-2Z" />}
      {name === 'history' && <>
        <path d="M3 10a9 9 0 1 1 2.2 8M3 4v6h6" />
        <path d="M12 7v5l3 2" />
      </>}
      {name === 'send' && <>
        <path d="m4 3 17 9-17 9 3.5-9Z" />
        <path d="M7.5 12H21" />
      </>}
      {name === 'copy' && <><rect x="8" y="3" width="13" height="13" rx="2" /><path d="M16 16v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h3" /></>}
      {name === 'check' && <path d="m5 12 4 4L19 6" />}
      {name === 'help' && <><circle cx="12" cy="12" r="9" /><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01" /></>}
      {name === 'eye' && <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12" /><circle cx="12" cy="12" r="3" /></>}
      {name === 'terminal' && <>
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="m7 9 3 3-3 3m6 0h4" />
      </>}
      {name === 'files' && <><path d="M7 3h10l3 3v12H7Zm-3 4v14h13M16 3v4h4M10 11h7m-7 4h5" /></>}
      {['file-read', 'file-write', 'file-edit'].includes(name) && <>
        <path d="M13 3H5v18h14V8Zm0 0v5h6" />
        {name === 'file-read' && <path d="M8 12h8m-8 4h6" />}
        {name === 'file-write' && <path d="M12 11v7m-3-3.5h6" />}
        {name === 'file-edit' && <path d="m9 18 1-4 6-6 3 3-6 6Zm1-4 3 3" />}
      </>}
      {name === 'memories' && <g transform="rotate(45 12 12)"><path d="M8 3h8l-1 7 4 4v2H5v-2l4-4ZM12 16v6"/></g>}
      {name === 'sparkle' && <path d="M12 2C10.8 9.2 9.2 10.8 2 12c7.2 1.2 8.8 2.8 10 10 1.2-7.2 2.8-8.8 10-10-7.2-1.2-8.8-2.8-10-10Z"/>}
      {name === 'database' && <><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0"/></>}
      {name === 'search' && <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></>}
      {name === 'globe' && <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a17 17 0 0 1 0 18 17 17 0 0 1 0-18" /></>}
      {name === 'link' && <><path d="m10 13 4-4M9 15l-2 2a4 4 0 0 1-5-5l4-4a4 4 0 0 1 6 0m0 8a4 4 0 0 0 6 0l4-4a4 4 0 0 0-5-5l-2 2" /></>}
      {name === 'browser' && <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 9h18M6 6.5h.01M9 6.5h.01" /></>}
      {name === 'pointer' && <path d="m5 3 3 17 4-6 7-1Zm7 11 4 7" />}
      {name === 'keyboard' && <><rect x="2" y="6" width="20" height="13" rx="2" /><path d="M5 10h1m3 0h1m3 0h1m3 0h2M5 14h1m3 0h1m3 0h1m3 0h2M8 16.5h8" /></>}
      {name === 'upload' && <path d="M4 15v5h16v-5M12 15V3m-5 5 5-5 5 5" />}
      {name === 'download' && <path d="M4 15v5h16v-5M12 3v12m-5-5 5 5 5-5" />}
      {name === 'refresh' && <path d="M20 9a8 8 0 1 0 0 6M20 3v6h-6" />}
      {name === 'sync' && <path d="M20 7a9 9 0 0 0-15-2L2 8m0-5v5h5M4 17a9 9 0 0 0 15 2l3-3m0 5v-5h-5"/>}
      {name === 'forward' && <path d="m13 5 7 7-7 7M20 12H4" />}
      {name === 'hand' && <path d="M8 12V5a2 2 0 0 1 4 0v7-8a2 2 0 0 1 4 0v8-6a2 2 0 0 1 4 0v9c0 4-3 6-6 6h-2c-3 0-4-2-6-4l-3-4a2 2 0 0 1 3-2l2 2" />}
      {name === 'checklist' && <path d="m3 6 1.5 1.5L7 5m3 1h11M3 12h4m3 0h11M3 18h4m3 0h11" />}
      {name === 'agents' && <><circle cx="9" cy="7" r="3" /><path d="M3 20v-2a6 6 0 0 1 12 0v2m1-16a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v2" /></>}
      {name === 'workflow' && <><rect x="3" y="3" width="6" height="6" rx="1" /><rect x="15" y="15" width="6" height="6" rx="1" /><path d="M9 6h5a4 4 0 0 1 4 4v5M6 9v9h9" /></>}
      {name === 'tool' && <path d="m14 7 4-4a6 6 0 0 1-7 8l-7 7a2 2 0 0 0 3 3l7-7a6 6 0 0 0 7-8l-4 4Z" />}
      {name === 'stop' && <rect x="6" y="6" width="12" height="12" rx="2" />}
      {name === 'plus' && <path d="M12 4v16M4 12h16" />}
      {name === 'close' && <path d="m6 6 12 12M18 6 6 18" />}
      {name === 'chevron' && <path d="m6 9 6 6 6-6" />}
      {name === 'back' && <path d="m11 5-7 7 7 7M4 12h16" />}
    </svg>
  )
}
