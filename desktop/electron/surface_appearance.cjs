/** Host-owned presentation only. No request data or executable content enters this stylesheet. */
const NATIVE_THEME_CSS = `
html{color-scheme:var(--nova-color-scheme,dark)}
html,body{background:var(--panel,#151413);color:var(--text,#ede9e3);font-family:var(--font,system-ui,sans-serif)}
body{border-color:var(--border,#9b7b50)}
.mark{color:var(--accent,#d5ad71)}
p,label,#question{color:var(--text-dim,#c9c2b7)}
dt,.foot,#path,#hint,#status{color:var(--text-muted,#a79b89)}
.details,textarea{border-color:var(--border,#494035);background:var(--code-bg,#100f0e);color:var(--text,#ede9e3)}
pre,#path{font-family:var(--font-code,ui-monospace,monospace);color:var(--text,#e7e0d5)}
button{border-color:var(--border,#796548);background:var(--bg-hover,#30291f);color:var(--text,#f5f0e8)}
button:hover{background:var(--panel-raised,#30291f);border-color:var(--accent,#d5ad71)}
button.allow,#confirm,#send{background:var(--accent,#d5ad71);color:var(--nova-accent-foreground,#1c170f);border-color:var(--accent,#d5ad71)}
button:focus-visible,textarea:focus-visible{outline-color:var(--accent,#d5ad71)}
textarea{caret-color:var(--accent,#d5ad71)}textarea:focus{border-color:var(--accent,#d5ad71)}
#status[role=alert]{color:var(--red,#e3b583)}
/* Match the main Nova window's rounded scrollbar in every dialog. */
*{scrollbar-width:auto;scrollbar-color:auto}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track,::-webkit-scrollbar-corner{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border,#2b2f39);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--text-muted,#484e5c)}
::-webkit-scrollbar-button{display:none;width:0;height:0}
`
function presentationCss(presentation) {
  const variables = presentation?.variables || {}
  const declarations = Object.entries(variables).filter(([key,value]) =>
    /^--[a-z0-9-]+$/.test(key) && typeof value === 'string' && value.length <= 512 && !/[\u0000-\u001f]/.test(value))
    .map(([key,value]) => `${key}:${value.replace(/</g,'\\3c ').replace(/>/g,'\\3e ')};`)
  declarations.push(`--nova-color-scheme:${variables['color-scheme'] === 'light' ? 'light' : 'dark'};`)
  return `:root{${declarations.join('')}}${NATIVE_THEME_CSS}`
}
function surfaceDocument(html, presentation) {
  return html.replace('</head>', `<style>${presentationCss(presentation)}</style></head>`)
}
function surfaceScale(parent){
  const factor=parent?.webContents?.getZoomFactor?.()
  return Number.isFinite(factor)&&factor>=.499&&factor<=1.501?Math.round(factor*100)/100:1
}
function surfaceBounds(parent,width,height){
  const area=parent.getContentBounds(),scale=surfaceScale(parent)
  width=Math.max(1,Math.round(Math.min(width*scale,area.width-32*scale)))
  height=Math.max(1,Math.round(Math.min(height*scale,area.height-32*scale)))
  return{x:Math.round(area.x+(area.width-width)/2),y:Math.round(area.y+(area.height-height)/2),width,height}
}
function applySurfaceZoom(child,parent){child.webContents.setZoomFactor?.(surfaceScale(parent))}
module.exports = { surfaceDocument, presentationCss, surfaceScale, surfaceBounds, applySurfaceZoom }
