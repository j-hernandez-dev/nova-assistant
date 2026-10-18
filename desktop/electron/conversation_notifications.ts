import type { Message } from '../src/types'

export type ConversationReadState = { observedIds: string[]; unreadIds: string[] }
export type ConversationPreferences = {
  load(sessionId: string): ConversationReadState | null
  save(sessionId: string, state: ConversationReadState): boolean
}

/** Presentation only. Application supplies message identity and completion.
 * Neither a token nor an agent Turn is a public-message notification. */
export class ConversationNotifications {
  private sessionId: string | null = null
  private observed = new Set<string>()
  private unread = new Set<string>()
  private initialized = false
  private visible = false
  private error: string | null = null
  private preferences?: ConversationPreferences

  setPreferences(preferences: ConversationPreferences) { this.preferences = preferences }
  beginHistoryImport() { this.initialized = false }
  get projection() {
    return { unreadCount: this.unread.size, historyVisible: this.visible, preferenceError: this.error }
  }
  private persist() {
    if (!this.sessionId || !this.preferences) return
    // Keep disk state bounded; on process restart the initial snapshot is a
    // baseline, so pruned old identities can never become new notifications.
    const observedIds = [...this.observed].slice(-10000)
    const retained = new Set(observedIds)
    try {
      const ok = this.preferences.save(this.sessionId, { observedIds,
        unreadIds: [...this.unread].filter(id => retained.has(id)) })
      this.error = ok ? null : 'CONVERSATION_PREFERENCES_SAVE_FAILED'
    } catch { this.error = 'CONVERSATION_PREFERENCES_SAVE_FAILED' }
  }
  setVisible(visible: boolean) {
    this.visible = visible
    if (visible && this.unread.size) { this.unread.clear(); this.persist() }
  }
  observe(sessionId: string, messages: Message[]) {
    if (sessionId !== this.sessionId) {
      this.sessionId = sessionId
      this.observed.clear(); this.unread.clear(); this.initialized = false; this.error = null
      let saved: ConversationReadState | null = null
      try { saved = this.preferences?.load(sessionId) || null } catch { /* defaults */ }
      saved?.observedIds.forEach(id => this.observed.add(id))
      saved?.unreadIds.forEach(id => this.unread.add(id))
    }
    const completed = messages.filter(message => message.role === 'assistant' &&
      message.deliveryStatus === 'completed' && message.content.trim())
    let changed = false
    for (const message of completed) {
      if (this.observed.has(message.id)) continue
      this.observed.add(message.id)
      if (this.initialized && !this.visible) this.unread.add(message.id)
      changed = true
    }
    // Resume/import is history, not a burst of newly generated responses.
    this.initialized = true
    const present = new Set(messages.map(message => message.id))
    for (const id of this.unread) {
      if (this.visible || !present.has(id)) { this.unread.delete(id); changed = true }
    }
    if (changed) this.persist()
    return this.projection
  }
}
