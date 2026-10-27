/** Native File handles cross the isolated bridge; caller-supplied paths do not. */
export function nativeSourcePaths(files:File[],pathForFile:(file:File)=>string):string[]{
  if(!Array.isArray(files)||!files.length||files.length>100)throw Error('Native files required')
  const paths=files.map(file=>pathForFile(file))
  if(paths.some(value=>!value))throw Error('Native files required')
  return paths
}
