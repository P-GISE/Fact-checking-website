import {lstat,realpath} from 'node:fs/promises';
import path from 'node:path';
import {z} from 'zod';

const identifier=z.string().uuid();
export function mediaDirectory(root:string,id:string):string{
 return path.join(path.resolve(root),identifier.parse(id));
}
export function incomingFile(root:string,name:string):string{
 return path.join(path.resolve(root),'.incoming',identifier.parse(name));
}
export async function readableMedia(root:string,id:string,storedPath:string):Promise<string>{
 const folder=mediaDirectory(root,id);
 const filename=path.basename(storedPath);
 if(!/^source\.(mp4|mp3|wav)$/.test(filename))throw new Error('INVALID_MEDIA_PATH');
 const target=path.join(folder,filename);
 if(storedPath!==target)throw new Error('INVALID_MEDIA_PATH');
 const canonicalRoot=await realpath(root);
 const canonicalTarget=await realpath(target);
 if(canonicalTarget!==path.join(canonicalRoot,id,filename)||(await lstat(target)).isSymbolicLink()||!(await lstat(target)).isFile())throw new Error('INVALID_MEDIA_PATH');
 return target;
}
