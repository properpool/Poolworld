# Pool World development log — 24 October 2026

## Production safety
The published `main/index.html` remains **unchanged** (prototype 0.3). Do not overwrite it with an unverified build. This development branch is a staging area only.

## Local v5.1 prototype (not yet uploaded to GitHub)
Source: `/mnt/data/POOL_WORLD_5.1_LOCAL_MATCH_TEST.html`
SHA-256: `c8d2f61f6142c5235636110df76082e735141b1b583752fce60760915d0534d4`
Based on `POOL_WORLD_5.0_FRESH_REBUILD.html`.

Changes made:
- Added local two-player turn handling, solids/stripes assignment, legal-contact/foul checks, and 8-ball win/loss handling.
- Added scratch recovery with ball-in-hand and tap-to-place cue positioning, rejecting overlaps and invalid locations.
- Added proper state restoration for retry/undo, reset and match-finished states.
- Rebalanced rolling resistance and set 85% power for break shots; a physical break now hits the rack.
- Preserved all four v3.9 embedded audio recordings byte-for-byte (verified SHA-256 comparisons).

Verification:
- JavaScript syntax: `node --check` passed.
- Headless Chromium / Playwright at 390x844 mobile viewport: no page errors or horizontal overflow.
- Actual browser SHOOT click triggers ball movement, followed by a settled turn.
- Physical break simulation: first object-ball collision recorded; settled in 939 fixed physics steps.
- Browser tests passed: cue scratch, ball-in-hand placement, invalid overlap rejection, undo, group assignment, switching turns, early 8-ball loss, legal 8-ball win, new rack and pointer aiming.
- 60 random physics shots completed and settled; no non-finite coordinates or stuck shots.

Tests/scripts:
`/mnt/data/patch_pool51.py`
`/mnt/data/test_pool51.py`
`/mnt/data/test_pool51_stress.py`

Limitations:
- Browser tests use Chromium emulation, not a physical Samsung handset.
- No full end-to-end human-style match has been completed in the browser; rule cases were exercised programmatically.
- The prototype remains 2D and is not yet visually or mechanically equivalent to Miniclip 8 Ball Pool.
- There is no GitHub-uploaded playable v5.1 build yet; preserve `main`.

Next:
1. Integrate and upload the verified local v5.1 source to this development branch, if the runtime can transfer the generated file to the GitHub connector.
2. Add repeatable end-to-end match tests and automated CI.
3. Improve cushions, pockets, shot dynamics, and on-device performance; do not begin graphics polish before gameplay stabilises.
