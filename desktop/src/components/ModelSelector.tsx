import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { useI18n } from '../i18n'
import { NovaIcon } from './NovaIcon'

type Props = { models: string[]; current: string; disabled: boolean; placeholder: string; title: string; onSelect: (model: string) => void }
/** An anchored select-only combobox; selection still goes through the existing model command. */
export function ModelSelector({ models, current, disabled, placeholder, title, onSelect }: Props) {
  const { t } = useI18n()
  const id = useId(), trigger = useRef<HTMLButtonElement>(null), menu = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false), [active, setActive] = useState(0)
  const [position, setPosition] = useState<CSSProperties>({ visibility: 'hidden' })
  const typed = useRef({ value: '', at: 0 })
  const locked = disabled || models.length === 0
  const listKey = models.join('\0')
  const activeIndex = Math.max(0, Math.min(active, models.length - 1))
  useEffect(() => { setOpen(false) }, [locked, current, listKey])
  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      const box = trigger.current?.getBoundingClientRect()
      if (!box) return
      const gap = 8, above = Math.max(0, box.top - gap * 2), below = Math.max(0, innerHeight - box.bottom - gap * 2)
      const up = above >= below, width = Math.min(320, Math.max(240, box.width), innerWidth - gap * 2)
      setPosition({ position: 'fixed', left: Math.max(gap, Math.min(box.right - width, innerWidth - width - gap)), width,
        maxHeight: Math.min(320, up ? above : below), ...(up ? { bottom: innerHeight - box.top + gap } : { top: box.bottom + gap }) })
    }
    const dismiss = (event: PointerEvent) => {
      if (!trigger.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) setOpen(false)
    }
    const blur = () => setOpen(false)
    const scroll = (event: Event) => { if (!menu.current?.contains(event.target as Node)) place() }
    place()
    const observer = new ResizeObserver(place)
    if (trigger.current) observer.observe(trigger.current)
    window.addEventListener('resize', place); window.addEventListener('scroll', scroll, true)
    document.addEventListener('pointerdown', dismiss, true); window.addEventListener('blur', blur)
    return () => { observer.disconnect(); window.removeEventListener('resize', place); window.removeEventListener('scroll', scroll, true)
      document.removeEventListener('pointerdown', dismiss, true); window.removeEventListener('blur', blur) }
  }, [open])
  useEffect(() => {
    if (open) document.getElementById(id + '-option-' + activeIndex)?.scrollIntoView({ block: 'nearest' })
  }, [open, activeIndex, id])
  function show() {
    if (locked) return
    typed.current = { value: '', at: 0 }; setActive(Math.max(0, models.indexOf(current))); setOpen(true)
  }
  function choose(index: number) {
    if (locked || !models[index]) return
    setOpen(false); trigger.current?.focus()
    if (models[index] !== current) onSelect(models[index])
  }
  function key(event: KeyboardEvent<HTMLButtonElement>) {
    if (locked) return
    if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); return }
    if (event.key === 'Tab') { setOpen(false); return }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) show()
      else setActive(index => (index + (event.key === 'ArrowDown' ? 1 : models.length - 1)) % models.length)
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault(); if (!open) show(); setActive(event.key === 'Home' ? 0 : models.length - 1)
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); if (open) choose(activeIndex); else show()
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault(); const now = Date.now()
      const prefix = (now - typed.current.at < 700 ? typed.current.value : '') + event.key.toLocaleLowerCase()
      typed.current = { value: prefix, at: now }
      const match = models.findIndex(model => model.toLocaleLowerCase().startsWith(prefix))
      if (!open) show()
      typed.current = { value: prefix, at: now }
      if (match >= 0) setActive(match)
    }
  }
  return <div className="nova-model-button" title={title}>
    <button type="button" className="nova-model-select" ref={trigger} role="combobox" aria-label={t('installedOllamaModels')}
      aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? id : undefined}
      aria-activedescendant={open ? id + '-option-' + activeIndex : undefined} value={current} disabled={locked}
      onKeyDown={key} onBlur={event => { if (!menu.current?.contains(event.relatedTarget as Node)) setOpen(false) }}
      onClick={() => { if (open) setOpen(false); else show() }}>
      <span className="nova-model-current">{models.includes(current) ? current : placeholder}</span>
    </button>
    <NovaIcon name="chevron" size={16} />
    {open && createPortal(<div id={id} ref={menu} className="nova-model-listbox" role="listbox" aria-label={t('installedOllamaModels')} style={position}
      onMouseDown={event => event.preventDefault()}>
      {models.map((model, index) => <div id={id + '-option-' + index} key={model} role="option" aria-selected={model === current}
        data-model={model} className={'nova-model-option' + (index === activeIndex ? ' active' : '') + (model === current ? ' selected' : '')}
        onPointerMove={() => setActive(index)} onClick={() => choose(index)} title={model}>
        <span>{model}</span>{model === current && <NovaIcon name="check" size={15} />}
      </div>)}
    </div>, document.body)}
  </div>
}
