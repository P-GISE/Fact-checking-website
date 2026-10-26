export function descendants(rows, rootPid, previouslyOwned = []) {
  const ids = new Set([rootPid, ...previouslyOwned.filter((old) => rows.some((row) => row.pid === old.pid && row.born === old.born)).map((old) => old.pid)]);
  let changed = true;
  while (changed) { changed = false; for (const row of rows) if (ids.has(row.parent) && !ids.has(row.pid)) { ids.add(row.pid); changed = true; } }
  return rows.filter((row) => ids.has(row.pid));
}

// Injected OS operations let tests exercise this same monitor/finally path.
export async function guardProcess({ child, parentPid, snapshot, softTree, hardTree, delay, now, signalBus,
  floorBytes, timeoutMs, outputExceeded = () => false }) {
  const owned = new Map();
  let rootBorn;
  let minimumFree = Infinity;
  let reason;
  let exited = false;
  let unresolved = false;
  let remaining = [];
  const started = now();
  const remember = (state) => {
    minimumFree = Math.min(minimumFree, state.freeBytes);
    const rootRow = state.rows.find((row) => row.pid === child.pid && row.parent === parentPid && row.node);
    if (!rootBorn && rootRow) rootBorn = rootRow.born;
    for (const row of descendants(state.rows, rootRow?.born === rootBorn && rootBorn ? child.pid : -1, [...owned.values()])) owned.set(`${row.pid}:${row.born}`, row);
    for(const row of state.ownedGroupMembers??[])owned.set(`${row.pid}:${row.born}`,row);
    if(state.ownershipUncertain)unresolved=true;
  };
  const live = (state) => {
    remember(state);
    const uncertain=(state.uncertainGroupMembers??[]).map(row=>({...row,ownership:'uncertain'}));
    return [...owned.values()].filter(old=>state.rows.some(row=>row.pid===old.pid&&row.born===old.born)&&!uncertain.some(row=>row.pid===old.pid&&row.born===old.born)).concat(uncertain);
  };
  const terminateHeldHandle = () => { try { if (!exited) child.kill('SIGTERM'); } catch { unresolved = true; } };
  const signal = () => { reason = 'signal'; terminateHeldHandle(); };
  child.once('exit', () => { exited = true; });
  child.once('error', () => { exited = true; reason = 'spawn_failed'; });
  signalBus.on('SIGTERM', signal); signalBus.on('SIGINT', signal);
  try {
    while (!exited) {
      const state = snapshot(); remember(state);
      if (state.freeBytes < floorBytes) reason = 'free_memory_floor';
      if (now() - started >= timeoutMs) reason = 'deadline';
      if (outputExceeded()) reason = 'output_limit';
      if (reason) break;
      await delay(3000);
    }
  } catch { reason = 'monitor_failed'; }
  finally {
    const cleanupDeadline = now() + 25000;
    try {
      const state = snapshot(); remember(state);
      const termTarget=state.rows.find(row=>row.pid===child.pid&&row.born===rootBorn)??state.ownedGroupMembers?.[0];
      if (!state.ownershipUncertain&&termTarget) softTree(termTarget.pid);
    } catch { unresolved = true; }
    terminateHeldHandle();
    await delay(2000);
    try {
      for (let pass = 0; pass < 3 && now() < cleanupDeadline; pass++) {
        remaining = live(snapshot());
        if (!remaining.length) break;
        for (const old of remaining) {
          if (now() >= cleanupDeadline) break;
          if(old.ownership==='uncertain'){unresolved=true;continue;}
          const current = snapshot().rows.find((row) => row.pid === old.pid && row.born === old.born);
          if (current) hardTree(old.pid);
        }
        await delay(1000);
      }
      remaining = live(snapshot());
    } catch { unresolved = true; }
    signalBus.off('SIGTERM', signal); signalBus.off('SIGINT', signal);
  }
  return { reason, minimumFree, unresolved: unresolved || !rootBorn, remaining,
    status: reason || (unresolved || !rootBorn || remaining.length ? 'cleanup_unresolved' : child.exitCode === 0 ? 'build_pass_smoke_pending' : 'build_failed') };
}
