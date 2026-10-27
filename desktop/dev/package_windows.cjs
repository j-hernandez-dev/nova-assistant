// Packaging is an explicit developer action. It never publishes a release.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process')
const root=path.resolve(__dirname,'../..')
if(process.platform!=='win32')throw Error('Windows x64 packaging requires Windows')
const checkoutPython=path.join(root,'.venv/Scripts/python.exe')
const python=process.env.NOVA_BUILD_PYTHON || (fs.existsSync(checkoutPython)?checkoutPython:'python')
const args=process.argv.slice(2)
for(let i=0;i<args.length;i++){
 if(args[i]==='--publish'&&args[i+1]==='never'){i++;continue}
 if(['--publish=never','--config.directories.output=release','-c.directories.output=release'].includes(args[i]))continue
 throw Error('This Windows build only permits --publish never and the release output directory')
}
const result=spawnSync(python,[path.join(root,'scripts/package_windows.py'),'--node',process.execPath],{cwd:root,stdio:'inherit',windowsHide:true})
if(result.error)throw result.error
process.exitCode=result.status===null?1:result.status
