import {useCallback,useEffect,useRef,useState} from 'react'
export function useModelVisibility(){
  const [hiddenModels,setHidden]=useState<string[]>([]),[ready,setReady]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(false)
  const pending=useRef(false)
  useEffect(()=>{
    let current=true
    void window.api.getModelVisibility().then(value=>{if(current){setHidden(value.hiddenModels);setReady(true)}}).catch(()=>{if(current)setError(true)})
    const off=window.api.onModelVisibilityChanged(value=>{if(current){setHidden(value.hiddenModels);setReady(true)}})
    return()=>{current=false;off()}
  },[])
  const save=useCallback(async(next:string[])=>{
    if(pending.current||!ready)return false
    pending.current=true;setBusy(true);setError(false)
    try{const result=await window.api.setModelVisibility({hiddenModels:next})
      if(!result.success){setError(true);return false}
      setHidden(result.preferences.hiddenModels);return true
    }catch{setError(true);return false}finally{pending.current=false;setBusy(false)}
  },[ready])
  return {hiddenModels,ready,busy,error,save}
}
export type ModelVisibilityState=ReturnType<typeof useModelVisibility>
