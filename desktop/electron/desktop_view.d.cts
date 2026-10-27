import type {BrowserWindow} from 'electron'
export const ZOOM_MIN:number,ZOOM_MAX:number,ZOOM_STEP:number
export function validZoomPercent(value:unknown):value is number
export function createDesktopView(options:{getWindow:()=>BrowserWindow|null;getPercent?:()=>number;savePercent?:(percent:number)=>unknown;onChange?:(percent:number)=>void}):{
  getPercent():number;change(direction:'in'|'out'):boolean;reset():boolean;attach(window:BrowserWindow):void
}
