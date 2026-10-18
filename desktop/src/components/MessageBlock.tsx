import type { Message } from '../types'
import { MessageFooter } from './MessageFooter'
import { Markdown } from './Markdown'
import { ActivityChain } from './TurnActivity'
import { collectActions } from '../turn_activity'
import { applicationErrorKey } from '../activity_presentation'
import { useI18n } from '../i18n'

type Props = { message: Message; approvalToolCallIds?: string[]; showActivity?: boolean }

export function MessageBlock({ message, approvalToolCallIds = [], showActivity = true }: Props) {
  const { t } = useI18n()
  const { role, content, toolCalls, toolResults, streaming, thinking, harnessEvents, toolActivities } = message
  const interrupted = message.deliveryStatus === 'cancelled' || message.deliveryStatus === 'failed'
  const hasToolFailure = toolActivities?.some(activity => ['failed', 'denied', 'outcome_unknown'].includes(activity.status))
  const messageLabel = role === 'user' ? 'userMessage' : role === 'system' ? 'systemMessage' : 'novaMessage'
  const styleRole = role === 'user' || role === 'system' ? role : 'assistant'
  const actions = showActivity ? collectActions([message], toolActivities || []) : []
  const writing = !!streaming && !interrupted && !toolActivities?.length && !toolCalls?.length

  if (!showActivity && !content && (!interrupted || message.deliveryStatus === 'failed' && hasToolFailure) && !message.knowledgeCitations) return null

  return <article className={`msg nova-message nova-message-${styleRole}`} aria-label={t(messageLabel)}>
    {content && <div className="msg-prompt nova-message-bubble">
      <span className={`msg-body ${role === 'system' ? 'error' : role === 'user' ? 'user' : 'agent'}`}>
        {role === 'system' && message.errorCode ? <>
          {t(applicationErrorKey(message.errorCode))}
          <details className="nova-activity-diagnostics"><summary>{t('diagnosticDetails')}</summary><pre>{message.errorCode}{'\n'}{content}</pre></details>
        </> : role === 'assistant' ? <Markdown text={content} streaming={writing} /> : content}
      </span>
    </div>}

    {showActivity && role === 'assistant' && thinking && !interrupted && !content && !toolActivities?.length && !toolCalls?.length && (
      <div className="msg-prompt nova-message-bubble"><span className="msg-body agent"><span className="thinking-indicator">
        <span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" />
        <span className="thinking-label">{t('thinking')}</span>
      </span></span></div>
    )}

    {actions.length > 0 && <ActivityChain actions={actions} approvalToolCallIds={approvalToolCallIds} />}

    {interrupted && !(message.deliveryStatus === 'failed' && hasToolFailure) && <p className="nova-message-terminal-note" role="status">
      {t(message.deliveryStatus === 'cancelled' ? 'responseInterrupted' : 'responseFailed')}
    </p>}

    {message.knowledgeCitations && <details aria-label={t('knowledgeCitations')}>
      <summary>{t('structuralSources')}</summary>
      {message.knowledgeCitations.valid.map(citation => <div key={citation.citationId}>
        [{citation.citationId}] {citation.displayLabel} — {t('revision')} {citation.revisionId}
        <pre>{JSON.stringify(citation.locator)}</pre>
        <button onClick={() => void window.api.knowledgeCommand('source_detail', { sourceId: citation.sourceId, revisionId: citation.revisionId })}>{t('sourceRevisionDetail')}</button>
      </div>)}
      {message.knowledgeCitations.invalid.length > 0 && <div>{t('invalidReferences')}: {message.knowledgeCitations.invalid.join(', ')}</div>}
    </details>}
    <MessageFooter message={message} />
  </article>
}
