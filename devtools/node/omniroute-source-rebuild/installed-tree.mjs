import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { lstatSync,readFileSync,readdirSync,realpathSync } from 'node:fs';
import { join,relative,resolve,sep } from 'node:path';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const within=(root,path)=>path===root||path.startsWith(root+sep);
// npm's .bin and the two pinned workspace links are real inputs, never followed outside this boundary.
export function installedTreeDigest(root,sourceRoot,workspacePaths) {
  assert(!lstatSync(root).isSymbolicLink(),'installed_root_symlink');
  const base=realpathSync(root),source=realpathSync(sourceRoot);
  const workspaces=workspacePaths.map(path=>{const target=resolve(source,path);assert(within(source,target),'workspace_path_escape');const real=realpathSync(target);assert(within(source,real),'workspace_realpath_escape');return real;});
  const entries=[];
  function walk(folder) {
    for(const entry of readdirSync(folder,{withFileTypes:true}).sort((a,b)=>a.name<b.name?-1:a.name>b.name?1:0)) {
      const path=join(folder,entry.name),name=relative(base,path).split(sep).join('/');
      if(entry.isSymbolicLink()) {
        const target=realpathSync(path);assert(within(base,target)||workspaces.some(root=>within(root,target)),'installed_link_outside_pinned_inputs');
        entries.push([name,'link',relative(source,target).split(sep).join('/')]);
      }else if(entry.isDirectory())walk(path);
      else{assert(entry.isFile(),'installed_special_file');entries.push([name,'file',sha(readFileSync(path))]);}
    }
  }
  walk(base);return {files:entries.length,sha256:sha(JSON.stringify(entries))};
}
