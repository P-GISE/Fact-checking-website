import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
export const linuxProfile = 'linux-webpack-8192-20261026';
export function resolveProfile(platform, name, heap = '4096') {
  if (name === linuxProfile) {
    assert.equal(platform, 'linux', 'linux_profile_on_other_platform');
    assert.equal(heap, '8192', 'linux_profile_heap_mismatch');
    return { name, bundler: 'webpack', heapMb: 8192, preflightGiB: 12 };
  }
  assert(name === undefined || name === '', 'unknown_build_profile');
  assert(['4096','6144'].includes(heap), 'unsupported_explicit_heap_limit');
  return { name: 'legacy-local-turbopack', bundler: 'turbopack', heapMb: Number(heap), preflightGiB: 10 };
}
export function resolveNpmEntry(node, exists = existsSync, paths = {dirname,join,resolve}) {
  const candidates = [paths.join(paths.dirname(node),'node_modules/npm/bin/npm-cli.js'),paths.resolve(paths.dirname(node),'../lib/node_modules/npm/bin/npm-cli.js')];
  const found = candidates.find(exists);assert(found,'npm_js_entry_required');return found;
}
export function assertPinnedNode(version) { assert.equal(version,'v24.20.0','node_pin_mismatch'); }
