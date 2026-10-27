// Minimal markdown tokenizer for assistant output — zero dependencies.
//
// This module parses
// the safe, common subset (fences, headings, lists, tables, inline
// code/bold/links) into plain token objects; the Markdown component
// maps them to React elements.  Text stays text nodes end to end, so
// no HTML injection is possible by construction.
//
// Pure functions only (no React import): node can unit-test this file
// after a bare tsc compile.

export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'bold' | 'italic' | 'strike'; children: Inline[] }
  | { kind: 'link'; children: Inline[]; href: string }

export type Block =
  | { kind: 'p'; lines: Inline[][] }
  | { kind: 'heading'; level: number; inline: Inline[] }
  | { kind: 'code'; lang: string; text: string }
  | { kind: 'list'; ordered: boolean; items: Inline[][] }
  | { kind: 'table'; header: Inline[][]; rows: Inline[][][] }

const FENCE_RE = /^ {0,3}(`{3,}|~{3,})(.*)$/
const HEADING_RE = /^(#{1,6})\s+(.*)$/
const BULLET_RE = /^\s*[-*+]\s+(.*)$/
const ORDERED_RE = /^\s*\d+[.)]\s+(.*)$/
const TABLE_ROW_RE = /^\s*\|(.+)\|\s*$/
const TABLE_SEP_RE = /^\s*\|?\s*:?-{2,}.*\|.*$/

function codeSpan(text: string, start: number): { end: number; text: string } | null {
  const marker = /^`+/.exec(text.slice(start))?.[0]
  if (!marker) return null
  let close = text.indexOf(marker, start + marker.length)
  while (close >= 0) {
    if (text[close - 1] !== '`' && text[close + marker.length] !== '`') {
      let value = text.slice(start + marker.length, close).replace(/\n/g, ' ')
      if (value.startsWith(' ') && value.endsWith(' ') && /[^ ]/.test(value)) value = value.slice(1, -1)
      return { end: close + marker.length, text: value }
    }
    close = text.indexOf(marker, close + marker.length)
  }
  return null
}

function escaped(char: string | undefined): boolean {
  const code = char?.charCodeAt(0) || 0
  return code >= 33 && code <= 47 || code >= 58 && code <= 64
    || code >= 91 && code <= 96 || code >= 123 && code <= 126
}

function closeEmphasis(text: string, start: number, marker: string): number {
  for (let i = start + marker.length; i < text.length; i++) {
    if (text[i] === '\\' && escaped(text[i + 1])) { i++; continue }
    if (text[i] === '`') {
      const code = codeSpan(text, i)
      if (code) { i = code.end - 1; continue }
    }
    if (text[i] !== marker[0]) continue
    let length = 1
    while (text[i + length] === marker[0]) length++
    if (length >= marker.length && /\S/.test(text[i - 1])
        && !(marker.length === 1 && length % 2 === 0)
        && !(marker[0] === '_' && /[\p{L}\p{N}]/u.test(text[i + length] || ''))) {
      return i + length - marker.length
    }
    i += length - 1
  }
  return -1
}

function linkSpan(text: string, start: number): { end: number; label: string; href: string } | null {
  let depth = 1, close = start + 1
  for (; close < text.length; close++) {
    if (text[close] === '\\' && escaped(text[close + 1])) { close++; continue }
    if (text[close] === '`') {
      const code = codeSpan(text, close)
      if (code) { close = code.end - 1; continue }
    }
    if (text[close] === '[') depth++
    if (text[close] === ']' && --depth === 0) break
  }
  if (text[close + 1] !== '(') return null
  let end = close + 2
  depth = 1
  for (; end < text.length; end++) {
    if (text[end] === '\\' && escaped(text[end + 1])) { end++; continue }
    if (text[end] === '(') depth++
    if (text[end] === ')' && --depth === 0) break
  }
  if (depth !== 0) return null
  const href = text.slice(close + 2, end).replace(/\\([()\\])/g, '$1')
  if (!/^https?:\/\//i.test(href) || /[\s\x00-\x1f\x7f]/.test(href)) return null
  try { if (!['http:', 'https:'].includes(new URL(href).protocol)) return null } catch { return null }
  return { end: end + 1, label: text.slice(start + 1, close), href }
}

function inlineTokens(text: string, depth: number, links: boolean): Inline[] {
  if (depth > 16) return [{ kind: 'text', text }]
  const out: Inline[] = []
  const literal = (value: string) => {
    const last = out[out.length - 1]
    if (last?.kind === 'text') last.text += value
    else out.push({ kind: 'text', text: value })
  }
  for (let i = 0; i < text.length;) {
    if (text[i] === '\\' && escaped(text[i + 1])) { literal(text[i + 1]); i += 2; continue }
    if (text[i] === '`') {
      const code = codeSpan(text, i)
      if (code) { out.push({ kind: 'code', text: code.text }); i = code.end; continue }
      const marker = /^`+/.exec(text.slice(i))![0]
      literal(marker); i += marker.length; continue
    }
    if (links && text[i] === '[') {
      const link = linkSpan(text, i)
      if (link) {
        out.push({ kind: 'link', href: link.href, children: inlineTokens(link.label, depth + 1, false) })
        i = link.end; continue
      }
    }
    const marker = '*_~'.includes(text[i]) ? /^(\*{1,3}|_{1,3}|~~)/.exec(text.slice(i))?.[0] : undefined
    if (marker && /\S/.test(text[i + marker.length] || '')
        && !(marker[0] === '_' && /[\p{L}\p{N}]/u.test(text[i - 1] || ''))) {
      const close = closeEmphasis(text, i, marker)
      if (close >= 0) {
        let children = inlineTokens(text.slice(i + marker.length, close), depth + 1, links)
        if (marker.length === 3) children = [{ kind: 'italic', children }]
        out.push({ kind: marker === '~~' ? 'strike' : marker.length > 1 ? 'bold' : 'italic', children })
        i = close + marker.length; continue
      }
    }
    literal(text[i]); i++
  }
  return out
}

export function parseInline(text: string): Inline[] { return inlineTokens(text, 0, true) }

function splitTableRow(line: string): Inline[][] {
  const inner = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  const cells: string[] = []
  let cell = ''
  for (let i = 0; i < inner.length; i++) {
    if (inner[i] === '\\' && escaped(inner[i + 1])) { cell += inner.slice(i, i + 2); i++; continue }
    if (inner[i] === '`') {
      const code = codeSpan(inner, i)
      if (code) { cell += inner.slice(i, code.end); i = code.end - 1; continue }
    }
    if (inner[i] === '|') { cells.push(cell); cell = '' } else cell += inner[i]
  }
  cells.push(cell)
  return cells.map(value => parseInline(value.trim()))
}

export function parseMarkdown(text: string): Block[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let paragraph: Inline[][] = []

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({ kind: 'p', lines: paragraph })
      paragraph = []
    }
  }

  let i = 0
  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block (an unterminated fence swallows the rest —
    // graceful while a reply is still streaming).
    const fence = FENCE_RE.exec(line)
    if (fence) {
      flushParagraph()
      const lang = fence[2].trim()
      const closing = new RegExp('^ {0,3}' + fence[1][0] + '{' + fence[1].length + ',}\\s*$')
      const body: string[] = []
      i += 1
      while (i < lines.length && !closing.test(lines[i])) {
        body.push(lines[i])
        i += 1
      }
      i += 1 // skip the closing fence (or run past the end)
      blocks.push({ kind: 'code', lang, text: body.join('\n') })
      continue
    }

    const heading = HEADING_RE.exec(line)
    if (heading) {
      flushParagraph()
      blocks.push({
        kind: 'heading',
        level: heading[1].length,
        inline: parseInline(heading[2].trim()),
      })
      i += 1
      continue
    }

    // Table: a |row| line whose next line is the separator.
    if (
      TABLE_ROW_RE.test(line)
      && i + 1 < lines.length
      && TABLE_SEP_RE.test(lines[i + 1])
    ) {
      flushParagraph()
      const header = splitTableRow(line)
      const rows: Inline[][][] = []
      i += 2
      while (i < lines.length && TABLE_ROW_RE.test(lines[i])) {
        rows.push(splitTableRow(lines[i]))
        i += 1
      }
      blocks.push({ kind: 'table', header, rows })
      continue
    }

    const bullet = BULLET_RE.exec(line)
    const ordered = ORDERED_RE.exec(line)
    if (bullet || ordered) {
      flushParagraph()
      const isOrdered = !bullet
      const items: Inline[][] = []
      while (i < lines.length) {
        const item = isOrdered
          ? ORDERED_RE.exec(lines[i])
          : BULLET_RE.exec(lines[i])
        if (!item) break
        items.push(parseInline(item[1].trim()))
        i += 1
      }
      blocks.push({ kind: 'list', ordered: isOrdered, items })
      continue
    }

    if (line.trim() === '') {
      flushParagraph()
      i += 1
      continue
    }

    paragraph.push(parseInline(line))
    i += 1
  }
  flushParagraph()
  return blocks
}
