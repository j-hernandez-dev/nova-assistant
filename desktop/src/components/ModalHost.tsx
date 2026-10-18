import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Props = {
  open?: boolean
  children: ReactNode
  onClose: () => void
  label?: string
  labelledBy?: string
  className?: string
  closeOnEscape?: boolean
  closeOnBackdrop?: boolean
}

const FOCUSABLE = 'button, a[href], input, select, textarea, [tabindex], [contenteditable="true"]'

/** One mounted modal at a time is selected by App. Closing is presentation only. */
export function ModalHost({ children, onClose, label, labelledBy, className = '', open = true,
  closeOnEscape = true, closeOnBackdrop = true }: Props) {
  const overlay = useRef<HTMLDivElement>(null)
  const dialog = useRef<HTMLDivElement>(null)
  const returnFocus = useRef(typeof document === 'undefined' ? null : document.activeElement as HTMLElement | null)
  const latest = useRef({ onClose, closeOnEscape, closeOnBackdrop })
  latest.current = { onClose, closeOnEscape, closeOnBackdrop }

  useEffect(() => {
    if (!open) return
    const content = dialog.current
    const backdrop = overlay.current
    if (!content || !backdrop) return
    const siblings = Array.from(document.body.children).filter(element => element !== backdrop && element instanceof HTMLElement) as HTMLElement[]
    const originalInert = siblings.map(element => ({ element, inert: element.inert }))
    originalInert.forEach(({ element }) => { element.inert = true })
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const focusable = () => Array.from(content.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(element => {
      if (element.tabIndex < 0 || element.matches(':disabled') || element.closest('[hidden], [aria-hidden="true"], [inert]')) return false
      for (let ancestor: HTMLElement | null = element; ancestor && ancestor !== backdrop; ancestor = ancestor.parentElement) {
        const style = window.getComputedStyle(ancestor)
        if (style.display === 'none' || style.visibility === 'hidden') return false
      }
      return true
    })
    const focusFirst = () => (focusable()[0] || content).focus()
    focusFirst()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopImmediatePropagation()
        if (latest.current.closeOnEscape) latest.current.onClose()
      } else if (event.key === 'Tab') {
        const targets = focusable()
        const first = targets[0]
        const last = targets[targets.length - 1]
        if (!first) {
          event.preventDefault()
          content.focus()
        } else if (event.shiftKey && (document.activeElement === first || document.activeElement === content || !content.contains(document.activeElement))) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && (document.activeElement === last || !content.contains(document.activeElement))) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    const onFocusIn = (event: FocusEvent) => {
      if (!content.contains(event.target as Node)) focusFirst()
    }
    document.addEventListener('keydown', onKeyDown, true)
    document.addEventListener('focusin', onFocusIn)
    return () => {
      document.removeEventListener('keydown', onKeyDown, true)
      document.removeEventListener('focusin', onFocusIn)
      originalInert.forEach(({ element, inert }) => { element.inert = inert })
      document.body.style.overflow = originalOverflow
      if (returnFocus.current?.isConnected) returnFocus.current.focus()
    }
  }, [open])

  return createPortal(
    <div ref={overlay} className="overlay nova-modal-backdrop" data-exiting={!open || undefined} inert={!open} aria-hidden={!open || undefined} onClick={event => {
      if (open && event.target === event.currentTarget && latest.current.closeOnBackdrop) latest.current.onClose()
    }}>
      <div ref={dialog} className={className} role="dialog" aria-modal="true"
        aria-labelledby={labelledBy} aria-label={labelledBy ? undefined : label} tabIndex={-1}>
        {children}
      </div>
    </div>, document.body,
  )
}
