# Let’s View Competitive Quality Plan

## Goal

The product promise is not "the largest CCTV directory." It is: after a place
search, show four *different*, nearby, currently playable views as quickly as
possible, and replace a failed panel without repeating an existing picture.

## What comparable services do well

| Reference | Observed strength | Let’s View response |
| --- | --- | --- |
| Caltrans QuickMap | Separates cameras, incidents, closures, traffic speed and signs into explicit map layers; clearly marks an out-of-service camera. | Keep a camera's identity separate from its availability and show source/health evidence in the quality view rather than hiding a broken camera. |
| Ontario 511 | Combines camera imagery with roadwork, collisions, closures, weather, plow locations and a persistent "My Cameras" list. | Preserve favourites and add route-context signals only after the four-panel playback contract is met. |
| Official public camera portals | Prefer authoritative source metadata and expose source freshness rather than silently substituting unknown content. | Locked camera-to-stream mappings, staged candidate promotion, and source-specific freshness checks remain mandatory. |

The references are product inspiration, not a claim that they solve cross-source
live playback. Let’s View's differentiator remains multi-provider, four-panel
nearby playback with automatic recovery.

## Playback quality contract

Every search and every automatic replacement must satisfy these invariants:

1. Each visible slot has a unique camera ID, scene identity, and normalized
   playback identity.
2. A failed stream can use its own verified backup, but cannot occupy the same
   playback identity already reserved by another visible slot.
3. Catalog identity faults are different from an upstream outage. The first
   blocks promotion/deployment; the second preserves the last verified mapping,
   lowers its rank, and searches nearby alternatives.
4. A browser canary records the catalog identity and the source the browser
   actually attached to each panel. Duplicate actual sources are service-impact
   failures even when catalog metadata is distinct.

## Delivery roadmap

### Now: correctness and evidence

- Lock verified mappings and reject conflicting name, coordinate, camera ID, or
  stream ID updates.
- Reserve normalized playback identities across the grid before automatic
  failover. Never relax this rule simply to fill a fourth panel.
- Run segment-level HLS probes, not playlist-only probes.
- Publish browser-canary panel diagnostics for catalog and actual stream
  identity separately.

### Next: faster recovery

- Store first-frame latency and segment availability per source/region, then
  select a pre-warmed standby from a different source where possible.
- Add a short per-source circuit breaker: after repeated failures, stop opening
  new connections for that source for a bounded cooldown while retaining the
  camera's mapping.
- Add an explicit "3 verified + 1 recovering" state when fewer than four unique
  streams exist; never disguise it with a duplicate feed.

### Later: travel context without diluting playback

- Add traffic, incidents, closures, and weather as optional layers/cards, not
  as dependencies of video startup.
- Offer a stable "My Views" collection containing verified locations and their
  last successful cameras.
- Build regional/source SLOs from real first-frame, stall, fallback, and
  actual-stream-duplicate measurements.

## Success measures

- Four unique canonical catalog streams at initial render.
- Four unique actual browser sources after player attachment.
- Median and p95 first-frame time by region/source.
- Automatic failover time and percentage landing on a verified unique standby.
- Count of catalog identity violations (target: zero) versus external-origin
  outages (tracked separately, never silently rewritten into mappings).
