# Matching browser captures

Status: generated 2026-09-29 with Chrome Headless Shell 151.0.7922.34. capture-manifest.json status: passed. Source hashes match MANIFEST.json. Agent inspection recorded in docs/07-VALIDATION.md; owner review pending.

Run `npm run capture` from design/ after installing the development dependency and Chromium. The command writes 16 direct browser PNGs and capture-manifest.json here. It never substitutes print-rendered controls or layouts.

No existing file here should be treated as a verified baseline without a successful manifest for the current source hashes and visual inspection. See docs/12-CAPTURE-AND-PARITY.md.
