import { useEffect, useId, useState } from 'react'
import { useI18n } from '../i18n'
import { collectActions, groupElapsedSeconds, formatDuration, type ConversationGroup } from '../turn_activity'
import { ActivityChain } from './TurnActivity'
import { NovaIcon } from './NovaIcon'
import { MessageBlock } from './MessageBlock'

export function ConversationTurn({ group, activeTurnId, approvalToolCallIds = [], compact = false }: {
  group: ConversationGroup; activeTurnId?: string | null; approvalToolCallIds?: string[]; compact?: boolean
}) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false), [now, setNow] = useState(Date.now)
  const regionId = useId()
  const active = !!activeTurnId && group.turn?.id === activeTurnId
    || !group.turn && group.messages.some(message => message.streaming)
  useEffect(() => {
    if (!active) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active, group.id])
  const actions = collectActions(group.messages, group.activities)
  const seconds = groupElapsedSeconds(group, active, now)
  const timing = seconds === null ? active ? t('activityProcessing') : t('activity')
    : `${t(active ? 'activityProcessingFor' : 'activityWorkedFor')} ${formatDuration(seconds)}`
  // Preserve all public model prose. Only the last completed reply follows the action chain.
  const last = group.messages[group.messages.length - 1]
  const final = !active && last?.role === 'assistant' && !!last.content && !last.toolCalls?.length
    && !last.toolActivities?.length && !['failed', 'cancelled'].includes(last.deliveryStatus || '') ? last : undefined
  const commentary = group.messages.filter(message => message !== final)
  const hasResponse = group.messages.some(message => message.content) || actions.length > 0 || active
  return <>
    {!compact && group.user && <MessageBlock message={group.user} showActivity={false} />}
    {hasResponse && <section className={`nova-turn${compact ? ' nova-turn-compact' : ''}`} data-turn-id={group.turn?.id || group.id}
      aria-label={t('novaMessage')}>
      <button className="nova-turn-time" onClick={() => setExpanded(value => !value)} disabled={!actions.length}
        aria-expanded={actions.length ? expanded : undefined} aria-controls={actions.length ? regionId : undefined}>
        <span>{timing}</span>{!!actions.length && <NovaIcon name="chevron" size={13} className={`nova-time-chevron${expanded ? ' expanded' : ''}`} />}
      </button>
      {!compact && commentary.map(message => <MessageBlock key={message.id} message={message} showActivity={false} />)}
      <div id={regionId} className="nova-turn-actions">
        <ActivityChain actions={actions} active={active} approvalToolCallIds={approvalToolCallIds}
          expanded={expanded} onExpanded={setExpanded} />
      </div>
      {!compact && final && <MessageBlock message={final} showActivity={false} />}
    </section>}
  </>
}
