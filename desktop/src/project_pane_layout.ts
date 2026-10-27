export const PROJECT_PANE_STORAGE_KEY='nova.projectPane.width.v1'
export const PROJECT_PANE_MIN=240
export const PROJECT_PANE_MAX=600

export function projectPaneBounds(available:number,viewport:number,viewer=0){
  const space=viewport<=768?available-40:Math.min(available*.45,available-viewer-320)
  const maximum=Math.max(160,Math.min(PROJECT_PANE_MAX,Math.floor(space)))
  const minimum=Math.min(PROJECT_PANE_MIN,maximum)
  return {minimum,maximum,collapseAt:Math.min(200,minimum-40)}
}
export function projectPaneWidth(value:number,minimum:number,maximum:number){
  return Math.round(Math.max(minimum,Math.min(maximum,value)))
}
/** A presentation preference only, scoped to Nova's existing browser profile. */
export function readProjectPaneWidth():number|null{
  try{
    const saved=window.localStorage.getItem(PROJECT_PANE_STORAGE_KEY)
    const value=saved===null?NaN:Number(saved)
    return Number.isFinite(value)&&value>=160&&value<=PROJECT_PANE_MAX?Math.round(value):null
  }catch{return null}
}
export function saveProjectPaneWidth(value:number|null){
  try{
    if(value===null)window.localStorage.removeItem(PROJECT_PANE_STORAGE_KEY)
    else window.localStorage.setItem(PROJECT_PANE_STORAGE_KEY,String(value))
  }catch{/* Resizing still works when persistent presentation storage is unavailable. */}
}
