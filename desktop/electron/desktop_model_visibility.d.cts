export type ModelVisibility={hiddenModels:string[]}
export type ModelVisibilityResult={success:true;preferences:ModelVisibility}|{success:false;error:{code:string}}
export function createModelVisibilityStore(directory:string):{get():ModelVisibility;set(value:unknown):ModelVisibilityResult}
