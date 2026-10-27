import {useEffect,useId,useRef,useState,type ReactNode} from 'react'
import {useI18n} from '../i18n'
import {useAppearance} from '../appearance'
import {defaultAppearance,type AppearancePreferences} from '../../shared/desktop_appearance'
import {SettingsSelect} from './SettingsSelect'
import {NovaMascot} from './NovaMascot'
import '../appearance_settings.css'

/** Keep every detected family available for both roles, including a previously saved family. */
export function appearanceFontOptions(fonts:string[],selected:string,systemLabel:string,unavailableLabel:string,complete:boolean){
  const families=[...new Set(fonts.filter(family=>typeof family==='string'&&family.trim()&&family!=='system'))].sort((a,b)=>a.localeCompare(b))
  const options:{value:string;label:string;description?:string}[]=[{value:'system',label:systemLabel},...families.map(family=>({value:family,label:family}))]
  if(selected!=='system'&&!families.includes(selected))options.push({value:selected,label:selected,...(complete?{description:unavailableLabel}:{})})
  return options
}

/** Presentation changes are saved and acknowledged independently from runtime settings. */
export function AppearanceSettings({titleId,active=true}:{titleId:string;active?:boolean}){
  const {t}=useI18n(),{appearance,ready,saveState,saveAppearance,effectiveScheme}=useAppearance()
  const id=useId(),loadedFonts=useRef(false)
  const [fonts,setFonts]=useState<string[]>([]),[fontLoad,setFontLoad]=useState<'idle'|'loading'|'ready'|'failed'>('idle')
  const busy=saveState==='saving'||saveState==='unconfirmed',disabled=busy||!ready
  useEffect(()=>{
    if(!active||loadedFonts.current)return
    let current=true
    setFontLoad('loading')
    const timer=setTimeout(()=>{if(current){current=false;setFontLoad('failed')}},15000)
    const api=typeof window==='undefined'?undefined:window.api
    if(typeof api?.getDesktopFonts!=='function'){clearTimeout(timer);setFontLoad('failed')}
    else void api.getDesktopFonts().then(result=>{
      if(!current)return
      if(result.success&&Array.isArray(result.fonts)){
        setFonts(result.fonts);loadedFonts.current=true;setFontLoad('ready')
      }else setFontLoad('failed')
    }).catch(()=>{if(current)setFontLoad('failed')}).finally(()=>clearTimeout(timer))
    return()=>{current=false;clearTimeout(timer)}
  },[active])
  function change<K extends keyof AppearancePreferences>(key:K,value:AppearancePreferences[K]){void saveAppearance({...appearance,[key]:value})}
  function group(name:string,title:string,children:ReactNode){return <section className="nova-preferences-group" aria-labelledby={id+'-'+name}>
    <h3 id={id+'-'+name}>{title}</h3><div className="nova-settings-card nova-preferences-list" aria-busy={busy}>{children}</div>
  </section>}
  function row(name:string,label:string,hint:string,control:ReactNode){return <div className="nova-preference-row" data-appearance-row={name}>
    <div><span className="nova-setting-label">{label}</span><p id={id+'-'+name+'-hint'}>{hint}</p></div>{control}
  </div>}
  function toggle(key:'showStartupScreen'|'startupMotion'|'mascotMotion',label:string,hint:string){return row(key,label,hint,
    <input id={id+'-'+key} data-appearance={key} aria-label={label} className="nova-switch" type="checkbox" role="switch" checked={appearance[key]}
      disabled={disabled} aria-describedby={id+'-'+key+'-hint'} onChange={event=>change(key,event.target.checked)}/>)}
  const themeKey=effectiveScheme==='light'?'lightTheme':'darkTheme'
  return <div className="nova-appearance-settings">
    <div className="nova-settings-introduction nova-section-introduction">
      <div><h2 id={titleId}>{t('settingsAppearance')}</h2><p>{t('settingsAppearanceHint')}</p></div>
      <button type="button" className="nova-settings-reset" disabled={disabled} onClick={()=>void saveAppearance(defaultAppearance,true)}>{t('settingsReset')}</button>
    </div>
    {group('style',t('appearanceStyle'),<>
      {row('colorScheme',t('appearanceColorScheme'),t('appearanceColorSchemeHint'),<SettingsSelect id={id+'-colorScheme'} data-settings-select="colorScheme"
        aria-label={t('appearanceColorScheme')} aria-describedby={id+'-colorScheme-hint'} value={appearance.colorScheme} disabled={disabled}
        options={[{value:'system',label:t('generalSystem')},{value:'light',label:t('appearanceLight')},{value:'dark',label:t('appearanceDark')}]}
        onChange={value=>change('colorScheme',value as AppearancePreferences['colorScheme'])}/>)}
      {row('theme',t('appearanceTheme'),t('appearanceThemeHint'),<SettingsSelect id={id+'-theme'} data-settings-select="theme" aria-label={t('appearanceTheme')}
        aria-describedby={id+'-theme-hint'} value={appearance[themeKey]} disabled={disabled}
        options={[{value:'nova',label:'Nova'},{value:'synthwave84',label:"SynthWave '84"},{value:'matrix',label:'Matrix'},{value:'box',label:'Box'}]}
        onChange={value=>change(themeKey,value as AppearancePreferences['lightTheme'])}/>)}
    </>)}
    {group('typography',t('appearanceTypography'),<>
      {row('interfaceFont',t('appearanceInterfaceFont'),t('appearanceInterfaceFontHint'),<SettingsSelect id={id+'-interfaceFont'} data-settings-select="interfaceFont"
        aria-label={t('appearanceInterfaceFont')} aria-describedby={id+'-interfaceFont-hint'} value={appearance.interfaceFont} disabled={disabled}
        options={appearanceFontOptions(fonts,appearance.interfaceFont,t('generalSystem'),t('appearanceFontUnavailable'),fontLoad==='ready')}
        onChange={value=>change('interfaceFont',value)}/>)}
      {row('codeFont',t('appearanceCodeFont'),t('appearanceCodeFontHint'),<SettingsSelect id={id+'-codeFont'} data-settings-select="codeFont"
        aria-label={t('appearanceCodeFont')} aria-describedby={id+'-codeFont-hint'} value={appearance.codeFont} disabled={disabled}
        options={appearanceFontOptions(fonts,appearance.codeFont,t('generalSystem'),t('appearanceFontUnavailable'),fontLoad==='ready')}
        onChange={value=>change('codeFont',value)}/>)}
    </>)}
    {fontLoad==='loading'&&<p className="nova-appearance-font-status nova-settings-pending" role="status">{t('appearanceFontsLoading')}</p>}
    {fontLoad==='failed'&&<p className="nova-appearance-font-status nova-settings-pending" role="status">{t('appearanceFontsFailed')}</p>}
    {group('startup',t('appearanceStartupGroup'),<>
      {toggle('showStartupScreen',t('appearanceStartupScreen'),t('appearanceStartupHint'))}
      {toggle('startupMotion',t('appearanceStartupMotion'),t('appearanceStartupMotionHint'))}
    </>)}
    {group('mascot',t('appearanceMascotGroup'),<>
      {toggle('mascotMotion',t('appearanceMascotMotion'),t('appearanceMascotMotionHint'))}
      {row('mascotAppearance',t('appearanceMascotAppearance'),t('appearanceMascotAppearanceHint'),<SettingsSelect id={id+'-mascotAppearance'} data-settings-select="mascotAppearance"
        aria-label={t('appearanceMascotAppearance')} aria-describedby={id+'-mascotAppearance-hint'} value={appearance.mascotAppearance} disabled={disabled}
        options={[{value:'2d',label:'Nova 2D'},{value:'3d',label:'Nova 3D'}]}
        onChange={value=>change('mascotAppearance',value as AppearancePreferences['mascotAppearance'])}/>)}
      <figure className="nova-mascot-preview" aria-label={`${t('appearanceMascotPreview')}: ${appearance.mascotAppearance==='3d'?'Nova 3D':'Nova 2D'}`}>
        <figcaption>{t('appearanceMascotPreview')}</figcaption>
        {active&&<NovaMascot preview/>}
      </figure>
    </>)}
    {!ready&&<p className="nova-settings-pending" role="status">{t('appearanceLoading')}</p>}
    {saveState!=='idle'&&<p className={saveState==='failed'?'nova-settings-error':busy?'nova-settings-pending':'nova-settings-success'} role={saveState==='failed'?'alert':'status'}>
      {t(saveState==='failed'?'appearanceSaveFailed':saveState==='saving'?'settingsSaving':saveState==='unconfirmed'?'settingsSaveUnconfirmed':saveState==='reset'?'appearanceResetDone':'settingsSaved')}</p>}
  </div>
}
