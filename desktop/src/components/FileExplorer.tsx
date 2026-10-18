import { useState, useCallback, useEffect, useRef } from 'react'
import type { ProjectState, ProjectAction } from '../types'
import { useI18n, type TranslationKey } from '../i18n'
import { NovaIcon } from './NovaIcon'
import { mergeProjectEntries, projectErrorKey, projectPreviewMatches, sameProjectPath } from '../project_presentation'

type TreeNode = {
  name: string; path: string; isDirectory: boolean; isSymlink: boolean
  expanded: boolean; loading: boolean; children: TreeNode[] | null; error: TranslationKey | null; truncated: boolean; nextOffset: number | null
}
type Props = {
  projects: ProjectState | null; busy: boolean; errorCode: string | null
  onFileSelect: (path: string) => void
  onProjectAction: (action: ProjectAction, path?: string) => Promise<void>
  refreshKey?: number
}

/** Project selection is a host transaction; this component presents only confirmed state. */
export function FileExplorer({ projects, busy, errorCode, onFileSelect, onProjectAction, refreshKey }: Props) {
  const { t } = useI18n()
  const rootDir = projects?.activePath || null
  const [nodes, setNodes] = useState<TreeNode[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<TranslationKey | null>(null)
  const [truncated, setTruncated] = useState(false)
  const [nextOffset, setNextOffset] = useState<number | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const moreLock = useRef(false)
  const [menuPath, setMenuPath] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const revision = useRef(0)
  const activeRoot = useRef(rootDir)
  activeRoot.current = rootDir
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes

  useEffect(() => {
    if (!menuPath) return
    const outside = (event: PointerEvent) => { if (!menuRef.current?.contains(event.target as Node)) setMenuPath(null) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenuPath(null) }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [menuPath])
  useEffect(() => { setMenuPath(null) }, [rootDir, busy])

  const loadDirectory = useCallback(async (path: string, expectedRoot: string, offset = 0) => {
    const result = await window.api.listDir(path, offset)
    if (!sameProjectPath(activeRoot.current, expectedRoot)) throw { code: 'PROJECT_STALE_ROOT' }
    if (!result.success) throw result.error
    if (!projectPreviewMatches(result, expectedRoot, path)) throw { code: 'PROJECT_STALE_ROOT' }
    const sorted = result.entries.slice().sort((a, b) => a.isDirectory === b.isDirectory
      ? a.name.localeCompare(b.name) : a.isDirectory ? -1 : 1)
    return { truncated: !!result.limitReached, nextOffset: result.nextOffset, children: sorted.map(entry => ({
      name: entry.name, path: path.replace(/[\\/]+$/, '') + '/' + entry.name,
      isDirectory: entry.isDirectory, isSymlink: entry.isSymlink,
      expanded: false, loading: false, children: null, error: null, truncated: false, nextOffset: null,
    } as TreeNode)) }
  }, [])

  useEffect(() => {
    const request = ++revision.current
    setError(null); setTruncated(false); setNextOffset(null); setLoadingMore(false); moreLock.current = false; setLoading(!!rootDir)
    const expanded = new Set<string>()
    const collect = (items: TreeNode[]) => { for (const node of items) {
      if (node.expanded && !node.isSymlink) expanded.add(node.path)
      if (node.children) collect(node.children)
    } }
    collect(nodesRef.current)
    setNodes([])
    if (!rootDir) return
    const rebuild = async (path: string): Promise<{ children: TreeNode[]; truncated: boolean; nextOffset: number | null }> => {
      const loaded = await loadDirectory(path, rootDir)
      for (const node of loaded.children) if (node.isDirectory && !node.isSymlink && expanded.has(node.path)) {
        try { const child = await rebuild(node.path); Object.assign(node, { children: child.children, truncated: child.truncated, nextOffset: child.nextOffset, expanded: true }) }
        catch { /* A removed or inaccessible child remains collapsed. */ }
      }
      return loaded
    }
    void rebuild(rootDir).then(result => {
      if (request !== revision.current) return
      setNodes(result.children); setTruncated(result.truncated); setNextOffset(result.nextOffset); setLoading(false)
    }).catch(cause => {
      if (request !== revision.current) return
      setError(projectErrorKey(cause?.code)); setLoading(false)
    })
    return () => { revision.current += 1 }
  }, [rootDir, refreshKey, loadDirectory])

  const updateNode = useCallback((path: string, updater: (node: TreeNode) => TreeNode) => {
    const update = (items: TreeNode[]): TreeNode[] => items.map(node => node.path === path ? updater(node)
      : node.children ? { ...node, children: update(node.children) } : node)
    setNodes(current => update(current))
  }, [])
  const toggle = useCallback(async (node: TreeNode) => {
    if (node.loading || node.isSymlink || !rootDir) return
    if (node.expanded) { updateNode(node.path, current => ({ ...current, expanded: false })); return }
    if (node.children !== null) { updateNode(node.path, current => ({ ...current, expanded: true })); return }
    const request = revision.current
    updateNode(node.path, current => ({ ...current, loading: true, error: null }))
    try {
      const result = await loadDirectory(node.path, rootDir)
      if (request === revision.current) updateNode(node.path, current => ({ ...current,
        children: result.children, truncated: result.truncated, nextOffset: result.nextOffset, expanded: true, loading: false }))
    } catch (cause) {
      if (request === revision.current) updateNode(node.path, current => ({ ...current, loading: false,
        error: projectErrorKey((cause as { code?: string })?.code) }))
    }
  }, [rootDir, loadDirectory, updateNode])
  const loadMore = useCallback(async (node?: TreeNode) => {
    const offset = node ? node.nextOffset : nextOffset
    if (!rootDir || offset === null || moreLock.current || node?.loading) return
    const request = revision.current
    moreLock.current = true
    if (node) updateNode(node.path, current => ({ ...current, loading: true, error: null }))
    else { setLoadingMore(true); setError(null) }
    try {
      const result = await loadDirectory(node?.path || rootDir, rootDir, offset)
      if (request !== revision.current) return
      if (node) updateNode(node.path, current => ({ ...current,
        children: mergeProjectEntries(current.children || [], result.children),
        nextOffset: result.nextOffset, truncated: result.truncated, loading: false }))
      else { setNodes(current => mergeProjectEntries(current, result.children)); setNextOffset(result.nextOffset); setTruncated(result.truncated) }
    } catch (cause) {
      if (request !== revision.current) return
      const key = projectErrorKey((cause as { code?: string })?.code)
      if (node) updateNode(node.path, current => ({ ...current, loading: false, error: key }))
      else setError(key)
    } finally { if (request === revision.current) { moreLock.current = false; setLoadingMore(false) } }
  }, [rootDir, nextOffset, loadDirectory, updateNode])
  const action = (kind: ProjectAction, path?: string) => { setMenuPath(null); void onProjectAction(kind, path) }
  const disabled = busy || !!projects?.busy
  const visibleError = errorCode || projects?.error?.code
  return <section className="explorer nova-projects">
    <div className="explorer-header">
      <h2 className="explorer-title">{t('projects')}</h2>
      <button className="project-add-button" disabled={disabled || !projects} onClick={() => action('add')}
        title={t('projectAdd')} aria-label={t('projectAdd')}><NovaIcon name="plus" size={20} /></button>
    </div>
    {visibleError && <div className="project-action-error" role="alert">{t(projectErrorKey(visibleError))}</div>}
    {!projects && !visibleError && <p className="explorer-loading" role="status">{t('projectLoading')}</p>}
    <div className="project-folder-list">
      {projects?.folders.map(folder => {
        const selected = sameProjectPath(folder.path, rootDir)
        return <div className={`project-card ${selected ? 'selected' : ''}`} key={folder.path}>
          <button className="project-select-button" disabled={disabled || selected} aria-pressed={selected}
            onClick={() => action('select', folder.path)} title={folder.path}>
            <span className="project-card-heading"><NovaIcon name="folder" size={21} /><span>{folder.name}</span></span>
            <span className="project-card-path">{folder.path}</span>
            {folder.isDefault && <span className="project-default-label">{t('projectDefault')}</span>}
          </button>
          <div className="project-options" ref={menuPath === folder.path ? menuRef : undefined}>
            <button className="project-options-button" disabled={disabled} aria-haspopup="menu"
              aria-expanded={menuPath === folder.path} aria-label={`${t('projectOptions')}: ${folder.name}`}
              onClick={() => setMenuPath(current => current === folder.path ? null : folder.path)}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
                <circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" />
              </svg>
            </button>
            {menuPath === folder.path && <div className="project-context-menu" role="menu">
              <button role="menuitem" onClick={() => action('change', folder.path)}>{t('projectChange')}</button>
              <button role="menuitem" disabled={folder.isDefault} onClick={() => action('remove', folder.path)} title={t(folder.isDefault ? 'projectDefaultRequired' : 'projectRemoveHint')}>{t('projectRemove')}</button>
              <button role="menuitem" onClick={() => action('open', folder.path)}>{t('projectOpen')}</button>
            </div>}
          </div>
        </div>
      })}
    </div>
    {projects && !rootDir ? <div className="explorer-empty">
      <p>{t('projectEmpty')}</p><span className="explorer-hint">{t('projectEmptyHint')}</span>
      <button className="explorer-open-btn" disabled={disabled} onClick={() => action('select', projects.defaultPath)}>{t('projectUseDefault')}</button>
    </div> : <div className="explorer-tree" aria-label={t('projects')} aria-busy={loading}>
      {loading && <div className="explorer-loading" role="status">{t('projectFolderLoading')}</div>}
      {error && <div className="explorer-error" role="alert">{t(error)}</div>}
      {!loading && !error && rootDir && nodes.length === 0 && <div className="explorer-empty-dir">{t('projectEmptyDirectory')}</div>}
      <NodeList nodes={nodes} depth={0} onToggle={toggle} onFileSelect={onFileSelect} onLoadMore={loadMore} />
      {nextOffset !== null && <button className="explorer-show-more" disabled={loadingMore} onClick={() => void loadMore()}>{t(loadingMore ? 'projectFolderLoading' : 'projectMoreItems')}</button>}
      {truncated && <p className="project-list-limit">{t('projectListTruncated')}</p>}
    </div>}
  </section>
}
function NodeList({ nodes, depth, onToggle, onFileSelect, onLoadMore }: { nodes: TreeNode[]; depth: number;
  onToggle: (node: TreeNode) => void; onFileSelect: (path: string) => void; onLoadMore: (node: TreeNode) => void }) {
  const { t } = useI18n()
  return <>
    {nodes.map(node => <div key={node.path}>
      <button className={`explorer-node ${node.isDirectory ? 'dir' : 'file'} ${node.isSymlink ? 'symlink' : ''}`}
        style={{ paddingLeft: depth * 16 + 8 }} disabled={node.isSymlink || node.loading}
        aria-expanded={node.isDirectory && !node.isSymlink ? node.expanded : undefined}
        title={node.isSymlink ? `${node.path} — ${t('projectSymlink')}` : node.path}
        onClick={() => node.isDirectory ? onToggle(node) : onFileSelect(node.path)}>
        <span className="explorer-arrow">{node.isDirectory ? (node.expanded ? '▾' : '▸') : ''}</span>
        <span className="explorer-icon">{node.isDirectory ? <NovaIcon name="folder" size={16} /> : <FileIcon />}</span>
        <span className="explorer-name">{node.name}</span>
        {node.isSymlink && <span className="explorer-symlink-badge">↗</span>}
      </button>
      {node.loading && <div className="explorer-loading" style={{ paddingLeft: depth * 16 + 24 }}>{t('projectFolderLoading')}</div>}
      {node.error && <div className="explorer-error" role="alert" style={{ paddingLeft: depth * 16 + 24 }}>{t(node.error)}</div>}
      {node.expanded && node.children && <NodeList nodes={node.children} depth={depth + 1} onToggle={onToggle} onFileSelect={onFileSelect} onLoadMore={onLoadMore} />}
      {node.expanded && node.children?.length === 0 && <div className="explorer-empty-dir">{t('projectEmptyDirectory')}</div>}
      {node.expanded && node.nextOffset !== null && <button className="explorer-show-more" disabled={node.loading} onClick={() => onLoadMore(node)}>{t(node.loading ? 'projectFolderLoading' : 'projectMoreItems')}</button>}
      {node.expanded && node.truncated && <p className="project-list-limit">{t('projectListTruncated')}</p>}
    </div>)}

  </>
}
function FileIcon() { return <svg width="15" height="17" viewBox="0 0 15 17" fill="none" stroke="currentColor" aria-hidden="true">
  <path d="M3 1h6l4 4v11H3zM9 1v4h4M5 9h6M5 12h6" strokeWidth="1.2" /></svg> }
