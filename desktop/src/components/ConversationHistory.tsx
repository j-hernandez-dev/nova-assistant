import { Fragment, useEffect, useState } from 'react'
import type { ConversationGroup } from '../turn_activity'
import { historySections, numericDate, messageTime } from '../message_presentation'
import { useI18n } from '../i18n'
import { ConversationTurn } from './ConversationTurn'

export function ConversationHistory({ groups, activeTurnId, approvalToolCallIds }: {
  groups: ConversationGroup[]; activeTurnId?: string | null; approvalToolCallIds: string[]
}) {
  const { t, locale } = useI18n()
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    const refresh = () => {
      const current = new Date(); setNow(current)
      const midnight = new Date(current); midnight.setHours(24, 0, 0, 0)
      clearTimeout(timer); timer = setTimeout(refresh, midnight.getTime() - current.getTime() + 25)
    }
    refresh(); window.addEventListener('focus', refresh)
    return () => { clearTimeout(timer); window.removeEventListener('focus', refresh) }
  }, [])
  return <>{historySections(groups, now).map(({ group, separator }) => <Fragment key={group.id}>
    {separator && <div className="nova-history-day" aria-label={t('conversationDate')}>
      <time dateTime={separator.date.toISOString()}>{separator.archived ? `${t('historySavedDate')} ${numericDate(separator.date)}` : separator.today
        ? `${t('historyToday')} ${messageTime(separator.date, locale)}` : numericDate(separator.date)}</time>
    </div>}
    <ConversationTurn group={group} activeTurnId={activeTurnId} approvalToolCallIds={approvalToolCallIds} />
  </Fragment>)}</>
}
