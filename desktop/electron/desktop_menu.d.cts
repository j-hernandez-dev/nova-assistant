import type {BrowserWindow,Menu,MenuItemConstructorOptions} from 'electron'
type View={getPercent:()=>number;change:(direction:'in'|'out')=>unknown;reset:()=>unknown}
type Actions={quit:()=>unknown;newProject:()=>unknown;zoomIn:()=>unknown;zoomOut:()=>unknown;actualSize:()=>unknown}
export function desktopMenuTemplate(locale:string,actions:Actions,options?:{platform?:string;zoomPercent?:number;canAddProject?:boolean}):MenuItemConstructorOptions[]
export function createDesktopMenu(options:{Menu:typeof Menu;getWindow:()=>BrowserWindow|null;getLocale:()=>string;quit:()=>void;newProject?:()=>unknown;canAddProject?:()=>boolean;view?:View}):{
  setReady(value:boolean):void;open(position:unknown):Promise<{opened:boolean}>;dispose():void
}
