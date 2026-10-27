import type {CatalogModel} from './components/ModelPicker'
import type {PythonMessage} from './types'

export type LibraryFilters = {query:string;kind:'all'|'llm'|'embedding';capability:''|'tools'|'vision'|'thinking';local:boolean}
export type ModelVariant = {name:string;size_gb:number;size_label:string;context_length:number;cloud_only:boolean}
export type VariantResult = {variants:ModelVariant[];loading:boolean;error:boolean;offline:boolean;stale:boolean;syncedAt:number}
export type LibraryState = {filters:LibraryFilters;models:CatalogModel[];nextPage:number|null;page:number;source:'web'|'snapshot';loading:boolean;error:boolean;
  offline:boolean;stale:boolean;syncedAt:number;variants:Map<string,VariantResult>}
export const defaultLibraryFilters:LibraryFilters={query:'',kind:'all',capability:'',local:true}
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0
const familyId=/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/
function validModels(value:unknown):value is CatalogModel[]{
  return Array.isArray(value)&&value.every(m=>m&&familyId.test(m.name)&&
    ['name','display','description','category','params'].every(key=>typeof m[key]==='string')&&finite(m.size_gb)&&
    Array.isArray(m.tags)&&m.tags.every((tag:unknown)=>typeof tag==='string')&&typeof m.installed==='boolean'&&
    ['llm','embedding'].includes(m.kind)&&typeof m.cloud_only==='boolean')
}
function validMetadata(data:any){return data&&finite(data.syncedAt)&&data.syncedAt<=8_640_000_000_000&&typeof data.offline==='boolean'&&typeof data.stale==='boolean'}
type Pending={id:number;timer:ReturnType<typeof setTimeout>;page?:number;filters?:LibraryFilters;family?:string}

/** Only observes library metadata. Installation and inference use the existing host commands. */
export class PublicModelLibrary {
  state:LibraryState={filters:defaultLibraryFilters,models:[],nextPage:null,page:0,source:'web',loading:false,error:false,
    offline:false,stale:false,syncedAt:0,variants:new Map()}
  private listeners=new Set<(state:LibraryState)=>void>()
  private pending=new Map<'search'|'variants',Pending>()
  constructor(private send:(message:object)=>void,private nextId:()=>number,
    private schedule:typeof setTimeout=setTimeout.bind(globalThis),private cancel:typeof clearTimeout=clearTimeout.bind(globalThis)){}
  subscribe(listener:(state:LibraryState)=>void){this.listeners.add(listener);listener(this.state);return()=>{this.listeners.delete(listener)}}
  private patch(patch:Partial<LibraryState>){this.state={...this.state,...patch};for(const listener of this.listeners)listener(this.state)}
  private clear(kind:'search'|'variants'){const old=this.pending.get(kind);if(old)this.cancel(old.timer);this.pending.delete(kind)}
  private variant(family:string,value:VariantResult){const variants=new Map(this.state.variants);variants.set(family,value);this.patch({variants})}
  private fail(kind:'search'|'variants',pending:Pending){
    this.clear(kind)
    if(kind==='search')this.patch({loading:false,error:true})
    else if(pending.family){const old=this.state.variants.get(pending.family)!;this.variant(pending.family,{...old,loading:false,error:true})}
  }
  private request(kind:'search'|'variants',data:Record<string,unknown>,extra:Partial<Pending>){
    this.clear(kind)
    const pending:Pending={id:this.nextId(),timer:0 as any,...extra}
    pending.timer=this.schedule(()=>{if(this.pending.get(kind)===pending)this.fail(kind,pending)},45_000)
    this.pending.set(kind,pending)
    try{this.send({id:pending.id,type:kind==='search'?'library_search':'library_variants',...data})}catch{this.fail(kind,pending)}
  }
  search(filters:LibraryFilters=this.state.filters,refresh=false){
    filters={...filters,query:filters.query.trim().slice(0,200)}
    const same=JSON.stringify(filters)===JSON.stringify(this.state.filters)
    if(!refresh&&same&&(this.state.loading||this.state.page>0))return
    this.clear('search')
    this.patch({filters,models:same?this.state.models:[],page:0,nextPage:null,loading:true,error:false})
    this.request('search',{...filters,page:1,refresh,source:'auto'},{page:1,filters})
  }
  more(){
    if(this.state.loading||this.state.error||!this.state.nextPage)return
    const page=this.state.nextPage,filters={...this.state.filters}
    this.patch({loading:true,error:false});this.request('search',{...filters,page,source:this.state.source},{page,filters})
  }
  retry(){if(this.state.page&&this.state.nextPage){this.patch({error:false});this.more()}else this.search(this.state.filters,true)}
  variants(family:string,refresh=false){
    if(!familyId.test(family))return
    const old=this.state.variants.get(family)
    if(!refresh&&old&&(old.loading||old.variants.length))return
    // A collapsed family can be reopened after its cancelled request.
    const previous=this.pending.get('variants')
    if(previous?.family&&previous.family!==family){const before=this.state.variants.get(previous.family);if(before)this.variant(previous.family,{...before,loading:false})}
    this.variant(family,{variants:old?.variants||[],loading:true,error:false,offline:false,stale:false,syncedAt:old?.syncedAt||0})
    this.request('variants',{family,refresh},{family})
  }
  disconnected(){for(const [kind,pending]of [...this.pending])this.fail(kind,pending)}
  dispose(){for(const kind of [...this.pending.keys()])this.clear(kind);this.listeners.clear()}
  receive(message:PythonMessage){
    const found=[...this.pending].find(([,request])=>request.id===message.id)
    if(!found)return false
    const [kind,pending]=found,data=message.data as any
    if(message.type==='error'){this.fail(kind,pending);return true}
    if(kind==='search'&&message.type==='library_search'){
      if(!validMetadata(data)||!validModels(data.models)||data.page!==pending.page||!['web','snapshot'].includes(data.source)||
        data.query!==pending.filters!.query||data.kind!==pending.filters!.kind||data.local!==pending.filters!.local||data.capability!==pending.filters!.capability||
        !(data.nextPage===null||Number.isSafeInteger(data.nextPage)&&data.nextPage===data.page+1)){
        this.fail(kind,pending);return true
      }
      this.clear(kind)
      const models=new Map((data.page===1?[]:this.state.models).map((model:CatalogModel)=>[model.name,model]))
      for(const model of data.models)models.set(model.name,model)
      this.patch({models:[...models.values()],page:data.page,nextPage:data.nextPage,source:data.source,loading:false,error:false,
        syncedAt:data.syncedAt,offline:this.state.offline&&data.page>1||data.offline,stale:data.stale})
    }else if(kind==='variants'&&message.type==='library_variants'){
      if(!validMetadata(data)||data.family!==pending.family||!Array.isArray(data.variants)||!data.variants.length||!data.variants.every((v:any)=>
        v&&typeof v.name==='string'&&v.name.startsWith(pending.family+':')&&/^[a-zA-Z0-9._:-]+$/.test(v.name)&&finite(v.size_gb)&&
        typeof v.size_label==='string'&&finite(v.context_length)&&typeof v.cloud_only==='boolean')){
        this.fail(kind,pending);return true
      }
      this.clear(kind);this.variant(pending.family!,{...data,loading:false,error:false})
    }else return false
    return true
  }
}
