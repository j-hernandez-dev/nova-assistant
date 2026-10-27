/** Presentation only: acknowledgements never accept, reject or delete a proposal. */
export type ProposalReadState = {windowRead:string[];tabRead:string[]}
type Storage = {load():unknown;save(value:ProposalReadState):void}
const validId=(id:unknown):id is string=>typeof id==='string'&&id.length>0&&id.length<=128
const validKeys=(value:unknown):value is string[]=>Array.isArray(value)&&value.length<=512&&value.every(id=>typeof id==='string'&&id.length<=270)

/** Keep identities only. Proposal text is neither retained nor persisted for notifications. */
export function proposalNotificationIds(value:unknown):string[]|null{
  if(!Array.isArray(value)||value.length>512)return null
  const ids:string[]=[]
  for(const row of value){
    if(!row||typeof row!=='object'||!validId(row.jobId)||!row.proposal||!validId(row.proposal.proposalId))return null
    ids.push(JSON.stringify([row.jobId,row.proposal.proposalId]))
  }
  return [...new Set(ids)]
}

export class MemoryProposalNotifications{
  private ids:string[]=[]
  private windowRead=new Set<string>()
  private tabRead=new Set<string>()
  private windowVisible=false
  private tabVisible=false
  constructor(private storage?:Storage){
    try{
      const value=storage?.load() as Partial<ProposalReadState>|null
      if(value&&validKeys(value.windowRead)&&validKeys(value.tabRead)){
        this.windowRead=new Set(value.windowRead);this.tabRead=new Set(value.tabRead)
      }
    }catch{/* An unavailable presentation store must not block memory controls. */}
  }
  get counts(){return{window:this.ids.filter(id=>!this.windowRead.has(id)).length,tab:this.ids.filter(id=>!this.tabRead.has(id)).length}}
  private persist(){try{this.storage?.save({windowRead:[...this.windowRead],tabRead:[...this.tabRead]})}catch{/* Keep this run's acknowledgements. */}}
  observe(value:unknown){
    const ids=proposalNotificationIds(value);if(ids===null)return false
    this.ids=ids
    const present=new Set(ids)
    this.windowRead=new Set([...this.windowRead].filter(id=>present.has(id)))
    this.tabRead=new Set([...this.tabRead].filter(id=>present.has(id)))
    if(this.windowVisible)ids.forEach(id=>this.windowRead.add(id))
    if(this.tabVisible)ids.forEach(id=>this.tabRead.add(id))
    this.persist();return true
  }
  setWindowVisible(visible:boolean){
    this.windowVisible=visible
    if(visible){this.ids.forEach(id=>this.windowRead.add(id));this.persist()}
  }
  setTabVisible(visible:boolean){
    this.tabVisible=visible
    if(visible){this.ids.forEach(id=>this.tabRead.add(id));this.persist()}
  }
}
