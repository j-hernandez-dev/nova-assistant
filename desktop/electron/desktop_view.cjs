const ZOOM_MIN=50,ZOOM_MAX=150,ZOOM_STEP=10
const validZoomPercent=value=>Number.isInteger(value)&&value>=ZOOM_MIN&&value<=ZOOM_MAX&&value%ZOOM_STEP===0

/** Integer percentages avoid Chromium's exponential zoom levels and rounding drift. */
function createDesktopView({getWindow,getPercent=()=>100,savePercent=()=>{},onChange=()=>{}}){
  let percent=validZoomPercent(getPercent())?getPercent():100
  function apply(window=getWindow()){
    if(!window||window.isDestroyed()||window.webContents.isDestroyed())return false
    window.webContents.setZoomFactor(percent/100)
    return true
  }
  function set(next){
    if(!validZoomPercent(next)||next===percent)return false
    const window=getWindow()
    if(!window||window.isDestroyed()||window.webContents.isDestroyed())return false
    window.webContents.setZoomFactor(next/100)
    percent=next
    savePercent(percent)
    onChange(percent)
    return true
  }
  return{
    getPercent:()=>percent,
    change:direction=>direction==='in'?set(Math.min(ZOOM_MAX,percent+ZOOM_STEP)):direction==='out'?set(Math.max(ZOOM_MIN,percent-ZOOM_STEP)):false,
    reset:()=>set(100),
    attach(window){
      const contents=window.webContents
      // Pinch magnification is separate from page zoom; keep one bounded scale.
      Promise.resolve(contents.setVisualZoomLevelLimits(1,1)).catch(()=>{})
      const loaded=()=>{apply(window);onChange(percent)}
      const requested=(event,direction)=>{event.preventDefault();if(window===getWindow())this.change(direction)}
      contents.on('did-finish-load',loaded);contents.on('zoom-changed',requested)
      window.once('closed',()=>{contents.removeListener('did-finish-load',loaded);contents.removeListener('zoom-changed',requested)})
      apply(window)
    },
  }
}
module.exports={createDesktopView,validZoomPercent,ZOOM_MIN,ZOOM_MAX,ZOOM_STEP}
