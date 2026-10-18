import { useRef, useState } from 'react'
import { useI18n } from '../i18n'

/** The question itself lives in the same host-owned modal system as confirmations. */
export function QuestionModal() {
  const { t } = useI18n()
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const opening = useRef(false)
  async function open() {
    if (opening.current) return
    opening.current = true; setBusy(true); setFailed(false)
    try { setFailed(!(await window.api.reviewPendingQuestion()).success) }
    catch { setFailed(true) }
    finally { opening.current = false; setBusy(false) }
  }
  return <div className="nova-question-pending">
    <div className="nova-permission-pending" role="status"><span>{t('agentQuestion')}</span>
      <button disabled={busy} onClick={() => void open()}>{t('answerToAgent')}</button>
    </div>
    {failed && <p className="nova-permission-error" role="alert">{t('questionOpenFailed')}</p>}
  </div>
}
