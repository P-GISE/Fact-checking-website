# LazyCodex installer bundle: local source rebuild verified

Confirmed: lazycodex-ai5.1.33 declares dependencies={} but its real installer bundle embeds Zod4.6.5. The latest npm5.1.48 installer also embeds4.6.5, so a version-only upgrade does not fix CVE-2023-54404 / GHSA-mrhx-c7xc-m3w5 (HIGH; fixed4.6.6). This is a developer-tool bundle issue; public-site exploitability has not been established.

The bundle SHA and all four embedded dependency versions are in node/lazycodex-bundle.cdx.json. verify_bundled_inventory.py compares actual bytes and components before accepting that inventory. The main gate scans this SBOM separately; the historical finding was reproduced before remediation and the regenerated bundle now scans clean. run.py now requires the verified full installed-tree derivative receipt. Actual global harness installation/auth/model routing was not executed or changed.

The source-build plan below has been implemented locally using the pinned Bun1.4.4 runtime and independent installer build lock. Official source and build script remained unchanged. Final bundle SHA2567b5228933e2d3694a806c876d037a4ec51748fac4b433e992c2dde47c655d21a; actual Zod4.6.6, guarded CLI/dry-run and before1001/after1 regression passed. No harness install/global routing/auth change occurred. Linux validation remains pending.

Original minimal plan and rationale:

1. Official npm5.1.33 gitHead and v5.1.33 tag both identify7a752ab5a88c2d255b926aff1c687b6d91758d02, repository code-yeongyu/oh-my-openagent. Public source tar SHA256 b99aca096a292fe0aace5b8299408a6290417dea2a72d8f386449c7a1600e3da; size43,229,306 bytes. No private project source is needed.
2. Preserve upstream LICENSE/source; pin isolated Bun build runtime and verify its official archive hash. No global Bun/Node/Codex updates. npm metadata has no engines declaration; source workspace dependencies and actual Node24 installer compatibility still need verification.
3. Patch only the Zod dependency/lock resolution to4.6.6, preserving the existing official installer sources. Audit the full build graph and all four real bundled packages. Do not replace an embedded version label or fake a freshness marker.
4. Official script/build-codex-install.ts provides the narrow installer-only Bun.build(target=node, esm, packages=bundle) recipe and computes source/body markers from actual generated output. Rebuild that artifact using the official script, then preserve original npm version identity plus explicit security-overlay receipt/source SHA/diff/bundle SHA; never claim the output is an untouched upstream release.
5. Prove marker/source/body consistency, new real bundled Zod version, all-severity SCA, pure argument parsing/help/dry-run compatibility in an isolated HOME. Do not run actual harness installation, provider authentication, or model routing. Only after review integrate verified overlay and regenerate the SBOM from real bytes.

Sources:
- https://github.com/code-yeongyu/oh-my-openagent/blob/7a752ab5a88c2d255b926aff1c687b6d91758d02/script/build-codex-install.ts
- https://github.com/advisories/GHSA-mrhx-c7xc-m3w5

Source build and safe help/version/synthetic dry-run were performed; actual harness installation was not performed. The original HIGH report remains retained as historical evidence; regenerated actual bundle/build SCA is0.
