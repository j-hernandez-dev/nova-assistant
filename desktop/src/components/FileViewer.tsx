import { useState, useEffect } from 'react'
import { useI18n, type TranslationKey } from '../i18n'
import { fileBasename, projectErrorKey, projectPreviewMatches } from '../project_presentation'

type Props = { filePath: string; rootDir: string; refreshKey?: number; onClose: () => void }

export function FileViewer({ filePath, rootDir, refreshKey, onClose }: Props) {
  const { t } = useI18n()
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<TranslationKey | null>(null)
  const basename = fileBasename(filePath)
  const dir = filePath.slice(0, Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\')) + 1)
  useEffect(() => {
    let current = true
    setLoading(true); setContent(null); setError(null)
    void window.api.readFile(filePath).then(result => {
      if (!current) return
      if (!result.success) setError(projectErrorKey(result.error.code))
      else if (!projectPreviewMatches(result, rootDir, filePath)) setError('projectStaleRoot')
      else setContent(result.content)
      setLoading(false)
    }).catch(() => { if (current) { setError('projectActionFailed'); setLoading(false) } })
    return () => { current = false }
  }, [filePath, rootDir, refreshKey])
  return <section className="file-viewer" aria-label={t('projectPreviewTitle')}>
    <div className="file-viewer-header"><div className="file-viewer-path" title={filePath}>
      <span className="file-viewer-dir">{dir}</span><span className="file-viewer-name">{basename}</span>
    </div><button className="file-viewer-close" onClick={onClose} title={t('closePreview')} aria-label={t('closePreview')}>×</button></div>
    <div className="file-viewer-content">
      {loading && <div className="file-viewer-status" role="status">{t('projectPreviewLoading')}</div>}
      {!loading && error && <div className="file-viewer-status" role="alert">{t(error)}</div>}
      {!loading && !error && content !== null && <FileContent content={content} />}
    </div>
  </section>
}
function FileContent({ content }: { content: string }) {
  const lines = content.split('\n')
  return <div className="file-viewer-lines">{lines.map((line, index) => <div key={index} className="file-viewer-line">
    <span className="file-viewer-ln" aria-hidden="true">{index + 1}</span><span className="file-viewer-code">{line || '\n'}</span>
  </div>)}</div>
}
