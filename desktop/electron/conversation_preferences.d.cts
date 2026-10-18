export type ConversationReadState = { observedIds: string[]; unreadIds: string[] }
export function createConversationPreferencesStore(directory: string): {
  load(sessionId: string): ConversationReadState | null
  save(sessionId: string, state: ConversationReadState): boolean
}
