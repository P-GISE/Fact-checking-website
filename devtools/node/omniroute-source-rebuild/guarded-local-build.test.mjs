import test from 'node:test';
import assert from 'node:assert/strict';
import { descendants } from './guarded-local-build.mjs';
test('selects only build descendants, retaining tracked live orphans', () => {
  const rows = [{pid:1,parent:0,born:'a'},{pid:2,parent:1,born:'b'},{pid:3,parent:2,born:'c'},{pid:4,parent:0,born:'d'}];
  assert.deepEqual(descendants(rows, 1).map((r)=>r.pid), [1,2,3]);
  assert.deepEqual(descendants(rows.slice(1), 99, [{pid:2,born:'b'}]).map((r)=>r.pid), [2,3]);
});
test('does not retain reused PID or unrelated node', () => {
  assert.deepEqual(descendants([{pid:2,parent:0,born:'new'}], 99, [{pid:2,born:'old'}]), []);
});
