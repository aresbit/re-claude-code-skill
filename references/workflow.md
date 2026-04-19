# Workflow Notes

## What worked well

- `npm pack` preserved the published wrapper package and the platform-native tarball exactly as shipped.
- Reading the wrapper `package.json` immediately exposed the real platform dependency through `optionalDependencies`.
- The native Windows package contained a large `claude.exe` with an embedded printable fallback bundle.
- Searching for `// @bun @bytecode @bun-cjs` was a reliable anchor for locating the fallback source.
- Writing metadata next to the dumped bundle made later reasoning much easier because offsets, lengths, and duplicate copies were preserved.

## What to expect

- The executable may contain multiple identical copies of the fallback JS.
- The fallback bundle may not preserve `// src/...` path comments even when it remains readable.
- Structural diffs based on generic token extraction produce noise. Treat them as triage, not as final feature conclusions.

## Recommended interpretation order

1. Confirm package identity and version.
2. Confirm platform dependency.
3. Extract the largest fallback bundle region.
4. Record duplicate offsets.
5. Compare against a local baseline.
6. Split high-value semantic regions.
7. Only then write version-to-version feature conclusions.

## Good semantic anchors

- Slash command registrations such as `"/ultrareview"` or `$.command("plugin")`
- Hook schema literals such as `hook_event_name:E.literal("PreCompact")`
- Hook execution exports such as `executePreCompactHooks`
- Remote Control auth messages such as `BRIDGE_LOGIN_ERROR`
- Remote Control UI strings such as `/remote-control is active`

## Common pitfalls

- Assuming the first marker hit is the real bundle. Small marker-containing regions can exist before the main payload.
- Treating a successful string hit as proof of a complete module. Validate with neighboring code.
- Overfitting the split logic to one build. Prefer stable semantics over one-off byte offsets.
