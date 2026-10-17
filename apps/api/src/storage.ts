import {open,type FileHandle} from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {z} from 'zod';

const identifier=z.string().uuid();
export function mediaDirectory(root:string,id:string):string{
 return path.join(path.resolve(root),identifier.parse(id));
}
export function incomingFile(root:string,name:string):string{
 return path.join(path.resolve(root),'.incoming',identifier.parse(name));
}
export async function openMedia(root:string,id:string,storedPath:string):Promise<FileHandle>{
 const folder=mediaDirectory(root,id),filename=path.basename(storedPath);
 if(!/^source\.(mp4|mp3|wav)$/.test(filename)||storedPath!==path.join(folder,filename))throw new Error('INVALID_MEDIA_PATH');
 // Linux /proc anchors each lookup to an already-open directory. Never follow
 // an untrusted media-directory or source-file symlink between checking/opening.
 const base=await open(path.resolve(root),constants.O_RDONLY|constants.O_DIRECTORY);
 try{
  const directory=await open(`/proc/self/fd/${base.fd}/${id}`,constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);
  try{
   const source=await open(`/proc/self/fd/${directory.fd}/${filename}`,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
   try{
    if(!(await source.stat()).isFile())throw new Error('INVALID_MEDIA_PATH');
    return source;
   }catch(error){await source.close();throw error;}
  }finally{await directory.close();}
 }finally{await base.close();}
}
