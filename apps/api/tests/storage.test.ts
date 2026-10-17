import {it,expect} from 'vitest';
import {mkdtemp,mkdir,writeFile,rename,readFile,rm,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {openMedia} from '../src/storage.js';

it('keeps reading the opened source when its path is replaced',async()=>{
 const root=await mkdtemp(join(tmpdir(),'factlens-open-')),id=randomUUID();
 const folder=join(root,id),source=join(folder,'source.wav');
 await mkdir(folder);await writeFile(source,'original');
 let handle;
 try{
  handle=await openMedia(root,id,source);
  await rename(source,join(folder,'old.wav'));await writeFile(source,'replacement');
  expect(await handle.readFile('utf8')).toBe('original');
  expect(await readFile(source,'utf8')).toBe('replacement');
 }finally{await handle?.close();await rm(root,{recursive:true,force:true});}
});
it('keeps reading the opened source when its directory becomes a symlink',async()=>{
 const root=await mkdtemp(join(tmpdir(),'factlens-open-')),id=randomUUID();
 const folder=join(root,id),source=join(folder,'source.wav'),other=join(root,'other');
 await mkdir(folder);await writeFile(source,'original');await mkdir(other);await writeFile(join(other,'source.wav'),'replacement');
 let handle;
 try{
  handle=await openMedia(root,id,source);
  await rename(folder,join(root,'old'));await symlink(other,folder);
  expect(await handle.readFile('utf8')).toBe('original');
 }finally{await handle?.close();await rm(root,{recursive:true,force:true});}
});
