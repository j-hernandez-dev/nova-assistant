type ProjectState = {schemaVersion:1;defaultPath:string;activePath:string|null;
  folders:Array<{path:string;name:string;isDefault:boolean}>;busy:boolean;error?:{code:string}|null}
export function createProjectsHost(options: {directory:string;defaultPath:string;client:any;
  chooseDirectory:()=>Promise<{canceled:boolean;filePaths:string[]}>;
  bootstrapWorkspace?:(path:string)=>Promise<{success:boolean;error?:{code:string}}>;
  clearChat?:(path:string)=>Promise<{success:boolean;error?:{code:string}}>;
  openPath:(path:string)=>Promise<string>;publish?:(state:ProjectState)=>void}): {
  state():ProjectState;action(action:unknown,path?:unknown):Promise<any>;preferredPath():string;
  defaultPath:string;listDirectory(path:unknown,offset?:unknown):Promise<any>;readFile(path:unknown):Promise<any>;
  isChanging():boolean;sync():void;setError(code:string):void
}
