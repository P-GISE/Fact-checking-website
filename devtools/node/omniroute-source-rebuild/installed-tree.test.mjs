import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync,mkdirSync,writeFileSync,symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { installedTreeDigest } from './installed-tree.mjs';
test('npm internal and pinned workspace links are recorded; external links are rejected',()=>{
  const source=mkdtempSync(join(tmpdir(),'omni-installed-tree-'));const deps=join(source,'node_modules');mkdirSync(deps);mkdirSync(join(deps,'real'));writeFileSync(join(deps,'real','a.js'),'first');
  symlinkSync(join(deps,'real'),join(deps,'internal'),'junction');mkdirSync(join(source,'workspace'));symlinkSync(join(source,'workspace'),join(deps,'workspace'),'junction');
  const before=installedTreeDigest(deps,source,['workspace']);writeFileSync(join(deps,'real','a.js'),'changed');assert.notEqual(installedTreeDigest(deps,source,['workspace']).sha256,before.sha256);
  const outside=mkdtempSync(join(tmpdir(),'omni-outside-'));symlinkSync(outside,join(deps,'external'),'junction');assert.throws(()=>installedTreeDigest(deps,source,['workspace']));
});
