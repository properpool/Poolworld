# Pool World — Fair play and anti-cheat requirements

Status: Design requirements, not implemented security protections.

## Principles
- Pool is skill-first. No purchases may increase shot accuracy, power, spin, collision behaviour, or other competitive capabilities.
- Same physics, rules, and shot constraints for all competitors.
- Beginners should have fair matchmaking and accessible learning tools; fair play does not mean randomising outcomes to make everyone win.
- Never promise that cheating is impossible.

## Multiplayer architecture
- Authoritative server validates shot input, legal turns, ball state, fouls, ball-in-hand, rack and match outcome.
- Clients submit bounded shot parameters; never accept client-reported winners, scores, balances or final ball positions as authoritative.
- Use deterministic or tightly reconciled physics, sequence numbers, authenticated sessions, rate limits and replay protection.
- Protect progression, virtual currency and cosmetic purchases through server-side transaction records.
- Record privacy-conscious match events and replays for disputes; retention and access policies required.

## Detection and enforcement
- Flag impossible actions, protocol tampering, repeated suspicious input and automation indicators for review.
- Provide player reports, appeals, proportionate sanctions and protection against false positives.
- Do not treat high win rates or exceptional skill alone as proof of cheating.
- Publish understandable fair-play rules and community standards.

## Test requirements before public multiplayer
- Invalid shot parameters and out-of-turn requests rejected.
- Client-forged ball positions, match wins, balances and gifts rejected.
- Duplicate and replayed requests rejected.
- Disconnect/reconnect cannot create extra turns or double rewards.
- Match outcomes consistent across supported devices.
- Load, latency and security testing before launch.

## Sequencing
Build stable offline pool first. Before online play, design and test server-authoritative match handling. A browser-only client cannot provide strong anti-cheat assurances by itself.
