# Pool World — verified development baseline (24 October 2026)

## Source preservation
- Latest recovered local build: `POOL_WORLD_3.2_PRECISION_AIM.html` (not yet uploaded to this repository).
- Physics reference: `POOL_WORLD_0.9_PHYSICS_LAB.html`.
- The existing `index.html` on `main` is the older 0.3 shooting prototype. **Do not overwrite it until a replacement has passed tests.**

## Verified baseline checks
Nine automated Node.js regression checks ran successfully against the recovered 3.2 source:
1. Rack has exactly 16 uniquely numbered balls.
2. Rack starts stationary with no pocketed balls.
3. A moving cue ball cannot be struck again.
4. Zero-power shots leave the cue ball stationary.
5. A low-power cue-ball shot eventually stops.
6. Ball-in-hand placement rejects overlap with another ball.
7. Cue-ball scratch awards the opponent ball in hand.
8. Break shot without a pot passes the turn.
9. Pocketing the eight-ball early loses the match under the current rules.

**Limits:** These are logic-level checks, not full-match simulation, audio validation, Android device testing, or proof of polished physics. The initial test harness had a cross-JavaScript-realm array comparison issue; that was fixed in the test harness and all nine checks then passed.

## Next gates
1. Safely import recovered 3.2 into version-controlled source without replacing live `index.html`.
2. Expand tests to complete matches, first-contact fouls, pocket/cushion edge cases, ball-in-hand, touch controls, and shooting recovery.
3. Address rules and physics defects, then test in a real browser.
4. Publish to GitHub Pages only after regression tests and browser smoke tests pass.
5. Improve visuals/audio, AI, progression and later multiplayer.

Budget: £0. Preserve the current live version until a verified replacement is ready.