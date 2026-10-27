import {useId} from 'react'
import type {ProjectAction,ProjectState} from '../types'
import {useI18n} from '../i18n'
import {projectErrorKey} from '../project_presentation'
import {ProjectFolderMenu} from './ProjectFolderMenu'

export function ProjectsSettings({projects,busy,errorCode,onAction}:{projects:ProjectState|null;busy:boolean;errorCode:string|null;onAction:(action:ProjectAction,path?:string)=>Promise<void>}){
  const {t}=useI18n(),id=useId(),disabled=busy||!!projects?.busy||!projects
  const defaultFolder=projects?.folders.find(folder=>folder.isDefault)
  const folders=projects?.folders.filter(folder=>!folder.isDefault)||[]
  const error=errorCode||projects?.error?.code
  const row=(folder:NonNullable<ProjectState>['folders'][number])=><div className="nova-preference-row nova-project-setting-row" key={folder.path} data-project-folder={folder.path}>
    <div><h4>{folder.name}</h4><p title={folder.path}>{folder.path}</p></div>
    <ProjectFolderMenu folder={folder} disabled={disabled} onAction={onAction}/>
  </div>
  return <div className="nova-project-settings" aria-busy={busy||!!projects?.busy}>
    <div className="nova-settings-introduction nova-section-introduction"><div><h2>{t('settingsProjects')}</h2><p>{t('settingsProjectsHint')}</p></div>
      <button className="nova-settings-reset" type="button" disabled={disabled} onClick={()=>void onAction('reset-default')}>{t('settingsReset')}</button>
    </div>
    <section className="nova-preferences-group" aria-labelledby={id+'-default'}><h3 id={id+'-default'}>{t('settingsDefaultFolder')}</h3>
      <div className="nova-settings-card nova-preferences-list">{defaultFolder?row(defaultFolder):<p className="settings-hint" role="status">{t('projectLoading')}</p>}</div>
    </section>
    <section className="nova-preferences-group" aria-labelledby={id+'-folders'}><h3 id={id+'-folders'}>{t('settingsProjectFolders')}</h3>
      <div className="nova-settings-card nova-preferences-list">{folders.map(row)}
        {!folders.length&&<p className="settings-hint" role="status">{t(projects?'settingsNoProjectFolders':'projectLoading')}</p>}
      </div>
    </section>
    {error&&<p className="nova-settings-error" role="alert">{t(projectErrorKey(error))}</p>}
  </div>
}
