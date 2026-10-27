import {useId} from 'react'
import type {DesktopSessionView} from '../../shared/application'
import {useI18n} from '../i18n'
import {fileBasename} from '../project_presentation'
import {ModalHost} from './ModalHost'
import {MemoryRecords} from './MemoryRecords'
import {NovaIcon} from './NovaIcon'
import '../memories.css'

export type ProposalNotifications={counts:{window:number;tab:number};observe:(proposals:unknown)=>void;setTabVisible:(visible:boolean)=>void}
export function MemoryWindow({view,open=true,locked=false,onClose,proposalNotifications}:{view:DesktopSessionView|null;open?:boolean;locked?:boolean;onClose:()=>void;proposalNotifications?:ProposalNotifications}){
  const {t}=useI18n(),title=useId()
  return <ModalHost open={open} onClose={onClose} labelledBy={title} className="nova-memories-dialog nova-surface-dialog">
    <header className="memories-header nova-surface-header">
      <div><span className="nova-settings-eyebrow">Nova</span><h1 id={title}>{t('memoryRecords')}</h1></div>
      <button type="button" className="nova-dismiss-button memories-close" aria-label={t('closeDialog')} onClick={onClose}><NovaIcon name="close" size={20}/></button>
    </header>
    <div className="memories-project" title={view?.workspace||undefined}><NovaIcon name="folder" size={16}/><span>{t('memoriesCurrentProject')}</span><strong>{fileBasename(view?.workspace||'')||t('settingsUnknown')}</strong></div>
    <MemoryRecords key={view?.sessionId+':'+view?.workspace} view={view} active={open} locked={locked} proposalNotifications={proposalNotifications}/>
  </ModalHost>
}
