import type { ToolActivity as Activity } from '../types'
import { useI18n } from '../i18n'
import { activityExplanation, activityPresentation, activityStatusText, activityToolVisual, isTerminalActivity } from '../activity_presentation'
import { NovaIcon } from './NovaIcon'
import { actionTitle, type TurnAction } from '../turn_activity'

export function ToolActivityCard({ activity, awaitingPermission = false, compact = false }: {
  activity: Activity; awaitingPermission?: boolean; compact?: boolean
}) {
  const action = { key: activity.operationId, name: activity.name, args: activity.arguments, output: activity.output, receipt: activity }
  return <ActionDetails action={action} awaitingPermission={awaitingPermission} compact={compact} />
}

export function ActionDetails({ action, awaitingPermission = false, compact = false }: {
  action: TurnAction; awaitingPermission?: boolean; compact?: boolean
}) {
  const { t } = useI18n()
  const activity = action.receipt
  const presentation = activity ? activityPresentation(activity, awaitingPermission) : null
  const explanation = activity ? activityExplanation(activity, awaitingPermission) : null
  const hasStreams = !!(activity?.stdout || activity?.stderr)
  const visual = activityToolVisual(action.name)
  const title = actionTitle(action, t, awaitingPermission)
  const label = presentation ? activityStatusText(presentation, t) : ''
  const status = !presentation ? t('activityUnverified') : presentation.tone === 'warning'
    || (awaitingPermission && activity?.status === 'pending')
    || (activity && isTerminalActivity(activity) && !['pending', 'running'].includes(activity.status)) ? label : ''
  const command = typeof action.args.command === 'string' ? action.args.command : null
  return <details className={`nova-tool-activity nova-action-row nova-activity-${presentation?.tone || 'neutral'}${compact ? ' nova-activity-compact' : ''}`}
    data-operation-id={activity?.operationId} data-tool-call-id={activity?.toolCallId}>
    <summary className="nova-activity-summary" title={title}>
      <NovaIcon className="nova-action-icon" name={visual.icon} size={15} />
      <span className={`nova-activity-title${presentation?.running ? ' nova-working-text' : ''}`}>{title}</span>
      <NovaIcon className="nova-activity-expand" name="chevron" size={13} />
      {status && <span className="nova-activity-status">{status}</span>}
    </summary>
    <div className="nova-activity-body">
      <div className="nova-action-detail-heading"><span className="nova-action-detail-label"><NovaIcon name={visual.icon} size={14} />{t(visual.heading)}</span>
        {presentation && <span className={presentation.running ? 'nova-working-text' : undefined}>{label}</span>}</div>
      <pre className="nova-action-invocation">{command ? `$ ${command}` : JSON.stringify(action.args, null, 2)}</pre>
      {explanation && <p className="nova-activity-explanation">{t(explanation)}</p>}
      {hasStreams ? <>
        {activity?.stdout && <div className="nova-activity-output"><span>{t('activityStdout')}</span><pre>{activity.stdout}</pre></div>}
        {activity?.stderr && <div className="nova-activity-output"><span>{t('activityStderr')}</span><pre>{activity.stderr}</pre></div>}
      </> : action.output ? <div className="nova-activity-output"><span>{t('activityOutput')}</span><pre>{action.output}</pre></div> : null}
      {activity?.outputTruncated && <p className="nova-activity-explanation">{t('activityOutputTruncated')}</p>}
      {activity && <details className="nova-activity-diagnostics nova-action-diagnostics">
        <summary><NovaIcon className="nova-diagnostic-chevron" name="chevron" size={12} />{t('diagnosticDetails')}</summary>
        <dl>
          <dt>{t('activityToolName')}</dt><dd>{activity.name}</dd>
          <dt>{t('activityOperationId')}</dt><dd>{activity.operationId}</dd>
          <dt>{t('activityToolCallId')}</dt><dd>{activity.toolCallId}</dd>
          <dt>{t('activityReceipt')}</dt><dd>{activity.status} / {activity.operationStatus} / {activity.effectState}</dd>
          {activity.errorCode && <><dt>{t('activityErrorCode')}</dt><dd>{activity.errorCode}</dd></>}
          {activity.exitCode != null && <><dt>{t('activityExitCode')}</dt><dd>{activity.exitCode}</dd></>}
          {isTerminalActivity(activity) && activity.effectState === 'unknown' && <>
            <dt>{t('activityEffectsVerification')}</dt><dd>{t('activityEffectsNotVerified')}</dd>
          </>}
          {activity.cwd && <><dt>{t('activityWorkingDirectory')}</dt><dd>{activity.cwd}</dd></>}
        </dl>
        {command && <><span>{t('activityArguments')}</span><pre>{JSON.stringify(activity.arguments, null, 2)}</pre></>}
      </details>}
    </div>
  </details>
}
