import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtempSync, mkdirSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { patchManifest, confined } from './rebuild.mjs';

test('patches pinned dependencies and nested override without mutating input', () => {
  const original = { name: 'omniroute', version: '3.8.52', dependencies: { next: '16.3.8', react: '19.2.8' }, overrides: { 'monaco-editor': { dompurify: '^3.4.14' } } };
  const result = patchManifest(original);
  assert.equal(result.dependencies.next, '16.4.1');
  assert.equal(result.overrides['monaco-editor'].dompurify, '3.4.17');
  assert.equal(result.dependencies.react, '19.2.8');
  assert.equal(original.dependencies.next, '16.3.8');
  assert.throws(() => patchManifest({ ...original, version: '3.8.53' }));
});

test('build paths reject siblings, parent traversal and junctions', () => {
  const root = mkdtempSync(join(tmpdir(), 'omniroute-contract-'));
  assert.equal(confined(root, join(root, 'cache')), join(root, 'cache'));
  assert.throws(() => confined(root, root));
  assert.throws(() => confined(root, join(root, '..', 'outside')));
  const target = join(root, 'target'); mkdirSync(target);
  symlinkSync(target, join(root, 'link'), 'junction');
  assert.throws(() => confined(root, join(root, 'link', 'output')));
});
