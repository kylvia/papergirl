# Vendored from baoyu-skills

The TypeScript files in this directory (`wechat-api.ts`, `md-to-wechat.ts`,
`wechat-extend-config.ts`, `wechat-image-processor.ts`) are vendored from
[JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills), specifically
the `skills/baoyu-post-to-wechat/scripts/` directory.

Modifications:
- Replaced `spawnSync("npx", ["-y", "bun", ...])` with direct `spawnSync("bun", [...])`
  to remove the npm registry roundtrip on every invocation.
- Dropped the `baoyu-chrome-cdp` dependency (browser-based posting path is unused).

Upstream `baoyu-md` (npm dependency) carries the WTFPL license, adapted from
[doocs/md](https://github.com/doocs/md). See the published package's `src/LICENSE`
for the full text.

`baoyu-skills` itself is published without an explicit top-level LICENSE file.
This vendoring is done in good faith with attribution; if the original author
prefers a different arrangement, please open an issue at
[JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills).
