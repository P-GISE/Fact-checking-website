import assert from 'node:assert/strict';
import { readFileSync, readdirSync, readlinkSync } from 'node:fs';
import { basename, dirname, join, resolve, sep } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

export function parseStat(text) {
  const close=text.lastIndexOf(')');assert(close>0,'invalid_proc_stat');
  const pid=Number(text.slice(0,text.indexOf('(')).trim());const fields=text.slice(close+2).trim().split(/\s+/);
  const row={pid,parent:Number(fields[1]),group:Number(fields[2]),session:Number(fields[3]),born:fields[19]};
  assert(Number.isInteger(pid)&&/^\d+$/.test(row.born),'invalid_proc_identity');return row;
}
export function effectiveMemory(meminfo, limit, current) {
  const available=Number(/^MemAvailable:\s+(\d+)\s+kB/m.exec(meminfo)?.[1])*1024;
  const total=Number(/^MemTotal:\s+(\d+)\s+kB/m.exec(meminfo)?.[1])*1024;
  assert(Number.isFinite(available)&&Number.isFinite(total),'memory_snapshot_unavailable');
  if(limit!==undefined&&limit.trim()!=='max') {
    const cap=Number(limit.trim()),used=Number(current?.trim());
    assert(Number.isFinite(cap)&&cap>0&&Number.isFinite(used)&&used>=0,'invalid_cgroup_memory');
    const headroom=Math.max(0,cap-used);
    return {freeBytes:Math.min(available,headroom),totalBytes:Math.min(total,cap),hostAvailableBytes:available,cgroupHeadroomBytes:headroom,limitingMemorySource:available<headroom?'host':headroom<available?'cgroup':'tie'};
  }
  return {freeBytes:available,totalBytes:total,hostAvailableBytes:available,cgroupHeadroomBytes:null,limitingMemorySource:'host'};
}
function optional(path) { try {return readFileSync(path,'utf8');}catch(error){if(error.code==='ENOENT')return undefined;throw error;} }
export function linuxSnapshot() {
  assert.equal(process.platform,'linux');
  // Resolve the process's actual hierarchy, rather than assuming it runs in root cgroup.
  const cgroup=readFileSync('/proc/self/cgroup','utf8');
  const v2=/^0::(.*)$/m.exec(cgroup)?.[1];
  let base='/sys/fs/cgroup',relative=v2;
  if(v2===undefined) {
    const v1=/^\d+:[^\n]*\bmemory\b[^:]*:(.*)$/m.exec(cgroup)?.[1];
    assert(v1!==undefined,'cgroup_memory_hierarchy_unverified');base='/sys/fs/cgroup/memory';relative=v1;
  }
  const groupPath=resolve(base,relative.replace(/^\//,''));
  assert(groupPath===base||groupPath.startsWith(base+sep),'cgroup_path_outside_mount');
  const meminfo=readFileSync('/proc/meminfo','utf8');let memory=effectiveMemory(meminfo);const hostAvailableBytes=memory.freeBytes;let cgroupHeadroomBytes=null;let budgets=0;
  for(let path=groupPath;;path=dirname(path)) {
    const limit=optional(join(path,v2===undefined?'memory.limit_in_bytes':'memory.max'));
    const current=optional(join(path,v2===undefined?'memory.usage_in_bytes':'memory.current'));
    if(limit!==undefined){const capped=effectiveMemory(meminfo,limit,current);memory={freeBytes:Math.min(memory.freeBytes,capped.freeBytes),totalBytes:Math.min(memory.totalBytes,capped.totalBytes)};if(capped.cgroupHeadroomBytes!==null)cgroupHeadroomBytes=cgroupHeadroomBytes===null?capped.cgroupHeadroomBytes:Math.min(cgroupHeadroomBytes,capped.cgroupHeadroomBytes);budgets++;}
    if(path===base)break;
  }
  assert(budgets>0,'cgroup_memory_limits_unverified');
  const rows=[];
  for(const name of readdirSync('/proc'))if(/^\d+$/.test(name)) {
    try {const row=parseStat(readFileSync(`/proc/${name}/stat`,'utf8'));row.node=false;try{row.node=['node','nodejs'].includes(basename(readlinkSync(`/proc/${name}/exe`)));}catch(error){if(!['ENOENT','ESRCH','EACCES','EPERM'].includes(error.code))throw error;}rows.push(row);}
    catch(error){if(!['ENOENT','ESRCH','EACCES','EPERM'].includes(error.code))throw error;}
  }
  const limitingMemorySource=cgroupHeadroomBytes===null||hostAvailableBytes<cgroupHeadroomBytes?'host':cgroupHeadroomBytes<hostAvailableBytes?'cgroup':'tie';
  return {...memory,hostAvailableBytes,cgroupHeadroomBytes,limitingMemorySource,memoryBudgetsChecked:budgets,rows};
}
export function signalOwnedGroup(rootPid, pid, signal, snapshot=linuxSnapshot, send=process.kill) {
  const row=snapshot().rows.find((item)=>item.pid===pid);
  assert(row&&row.group===rootPid&&row.session===rootPid,'process_outside_owned_session');
  send(-rootPid,signal);
}
export function ownedLinuxAdapter(child,parentPid,read=linuxSnapshot,send=process.kill) {
  const known=new Map();let rootBorn;
  const snapshot=()=>{
    const state=read();const root=state.rows.find(r=>r.pid===child.pid&&r.parent===parentPid&&r.node&&r.group===child.pid&&r.session===child.pid);
    if(!rootBorn&&root)rootBorn=root.born;
    const active=state.rows.some(r=>known.get(r.pid)===r.born&&r.group===child.pid&&r.session===child.pid);
    const reused=rootBorn&&state.rows.some(r=>r.pid===child.pid&&r.born!==rootBorn);
    const anchored=!!rootBorn&&!reused&&((root&&root.born===rootBorn)||active);
    const members=state.rows.filter(r=>r.group===child.pid&&r.session===child.pid);
    if(anchored)for(const row of members)known.set(row.pid,row.born);
    return {...state,ownedGroupMembers:anchored?members:[],uncertainGroupMembers:anchored?[]:members,ownershipUncertain:!anchored&&members.length>0};
  };
  const signal=(pid,kind)=>{
    const state=snapshot();const row=state.ownedGroupMembers.find(r=>r.pid===pid);
    assert(!state.ownershipUncertain&&row&&known.get(pid)===row.born,'linux_process_identity_changed');
    signalOwnedGroup(child.pid,pid,kind,()=>({rows:[row]}),send);
  };
  return {snapshot,signal};
}
export async function confirmReaped(child, wait=sleep) {
  if(child.exitCode!==null||child.signalCode!==null)return true;
  const done=new Promise((accept)=>{child.once('exit',()=>accept(true));child.once('error',()=>accept(false));});
  const result=await Promise.race([done,wait(5000).then(()=>false)]);assert.equal(result,true,'child_not_reaped');return true;
}
