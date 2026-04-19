---
name: re-claude-code-skill
description: Reverse engineer Claude Code release artifacts by downloading npm packages, unpacking platform binaries, extracting embedded fallback JavaScript bundles from native executables, diffing them against a local baseline such as opencc, and semantically splitting commands, hooks, and Remote Control code into reusable chunks. Use when Codex needs to inspect Claude Code release packages, compare versions, study Bun/JSC fallback packaging, or build repeatable extraction workflows for Claude Code internals.
---

# RE Claude Code

Use this skill to turn a Claude Code npm release into readable artifacts and a reusable reverse-engineering workspace.

## Quick Workflow

1. Resolve the official npm package names and download the release tarballs with `npm pack`.
2. Unpack the wrapper package and the platform package separately.
3. Inspect the wrapper `package.json` first to confirm which optional platform dependency is actually used.
4. Treat the platform executable as the main target. First look for an embedded fallback JavaScript bundle before assuming bytecode-only packaging.
5. Extract the biggest printable region that contains the Bun bytecode marker `// @bun @bytecode @bun-cjs`.
6. Save the extracted bundle and a metadata file with start offset, length, hash, and duplicate offsets.
7. Compare the dumped bundle with a local baseline such as `opencc/dist/cli.js`.
8. If source path comments are stripped, split the bundle by semantic anchors instead of file-path markers.

## Practical Rules

- Prefer `npm pack` over ad hoc registry downloads so the exact published tarball is preserved.
- Keep the wrapper package and the platform package in separate directories. The wrapper is useful for dependency resolution; the platform package contains the real payload.
- Expect duplicate embedded bundle copies in the native executable. Record all duplicate offsets instead of assuming a single copy.
- Favor static extraction first. Only move to runtime hooking when the fallback source is absent or too incomplete.
- When diffing against `opencc`, treat automated token extraction as a noisy first pass. Use it for triage, then validate conclusions against concrete command names, hook schemas, and Remote Control strings.
- If `// src/...` path comments are unavailable, split by stable semantic anchors such as command registration strings, hook event literals, exported executor names, and Remote Control UX text.
- Keep every extraction step reproducible: write files, metadata, and manifest outputs instead of relying on terminal-only observations.

## Reusable Artifacts

### scripts/

Use the bundled scripts in order:

- `extract_bundle.py`
  Extract the largest printable fallback JS bundle from a Claude Code native executable and emit a metadata file.
- `compare_bundles.py`
  Generate a coarse structural diff between an official dumped bundle and a local baseline bundle.
- `extract_semantic_chunks.py`
  Carve high-value bundle regions into `commands/`, `hooks/`, and `remote-control/` directories using semantic anchors.

Run them like this:

```powershell
python scripts\extract_bundle.py package\claude.exe artifacts\claude.bundle.js
python scripts\compare_bundles.py artifacts\claude.bundle.js ..\opencc\dist\cli.js artifacts\bundle-diff-report.json
python scripts\extract_semantic_chunks.py artifacts\claude.bundle.js artifacts\semiauto-split
```

### references/

- Read [workflow.md](./references/workflow.md) when you need the rationale, pitfalls, and interpretation guidance behind the extraction flow.

## Interpretation Tips

- The wrapper npm package may be tiny even when the real platform package is large. That is expected.
- If the dumped bundle starts with `// @bun @bytecode @bun-cjs`, you likely extracted the fallback JS source rather than raw JSC bytecode.
- A smaller official bundle than `opencc/dist/cli.js` usually means stronger dead-code elimination or product-build pruning, not necessarily fewer features.
- Large semiauto chunks are acceptable on the first pass. Narrow them later by switching anchors from broad UX strings to specific function names or command registrations.

## Deliverables

When using this skill, aim to leave behind:

- the original tarballs
- unpacked wrapper and platform directories
- extracted bundle JS
- extraction metadata JSON
- structural diff report JSON
- semantically split chunk directories

If a step fails because the environment is missing a dependency, document the missing tool and continue with the highest-value fallback path.
