import { useState } from 'react'
import { useI18n } from '../i18n'
import { activeAction, actionTitle, chainLabel, chainIcon, type TurnAction } from '../turn_activity'
import { activityPresentation, activityToolVisual } from '../activity_presentation'
import { NovaIcon } from './NovaIcon'
import { ActionDetails } from './ToolActivity'

export function ActivityChain({ actions, active = false, approvalToolCallIds = [], expanded, onExpanded }: {
  actions: TurnAction[]; active?: boolean; approvalToolCallIds?: string[]; expanded?: boolean; onExpanded?: (value: boolean) => void
}) {
  const { t } = useI18n()
  const [ownExpanded, setOwnExpanded] = useState(false)
  const isOpen = expanded ?? ownExpanded
  const running = active ? activeAction(actions) : undefined
  const awaiting = !!running?.receipt && approvalToolCallIds.includes(running.receipt.toolCallId)
  const working = active && !awaiting && (!running || !!running.receipt && activityPresentation(running.receipt).running)
  const summary = running ? (awaiting ? t('activityAwaitingPermission') : actionTitle(running, t))
    : active ? t('thinking') : t(chainLabel(actions))
  const warning = !active && actions.some(action => action.receipt
    && activityPresentation(action.receipt).tone === 'warning')
  if (!actions.length) return active ? <p className="nova-thinking-line nova-working-text" role="status">{t('thinking')}</p> : null
  return <details className="nova-action-chain" open={isOpen} onToggle={event => {
    const next = event.currentTarget.open
    if (next !== isOpen) { setOwnExpanded(next); onExpanded?.(next) }
  }}>
    <summary className="nova-chain-summary" title={summary}>
      <NovaIcon className="nova-action-icon" name={running ? activityToolVisual(running.name).icon : active ? 'brain' : chainIcon(actions)} size={15} />
      <span className={`nova-chain-label${working ? ' nova-working-text' : ''}`} role={active ? 'status' : undefined}>{summary}</span>
      <NovaIcon className="nova-activity-expand" name="chevron" size={13} />
      {warning && <span className="nova-chain-warning">{t('activityNeedsReview')}</span>}
    </summary>
    <div className="nova-action-list" aria-label={t('activityActions')}>
      {actions.map(action => <ActionDetails key={action.key} action={action}
        awaitingPermission={!!action.receipt && approvalToolCallIds.includes(action.receipt.toolCallId)} />)}
    </div>
  </details>
}
