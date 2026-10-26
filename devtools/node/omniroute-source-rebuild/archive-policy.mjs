import assert from 'node:assert/strict';
export const canonicalGitOptions=['--no-replace-objects','-c','core.autocrlf=false','-c','core.eol=lf','-c','tar.umask=0002'];
export function canonicalArchiveArgs(commit){assert.match(commit,/^[a-f0-9]{40}$/);return [...canonicalGitOptions,'archive','--format=tar',commit];}
export function canonicalGitEnv(env){return {...env,GIT_NO_REPLACE_OBJECTS:'1'};}
export function verifyCommitTree(actualCommit,actualTree,plan){assert.equal(actualCommit,plan.commit,'unexpected_source_commit');assert.match(plan.sourceTree,/^[a-f0-9]{40}$/);assert.equal(actualTree,plan.sourceTree,'unexpected_source_tree');}
