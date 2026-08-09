# OSM Bundle Architecture

## Core Model

The central concept is the **OSM Bundle Viewport**.

- It defines how much OSM data is fetched.
- It defines cache identity for shared OSM artifacts.
- It is independent from visual style tweaks.

`BundleViewportPolicy` is a subordinate mechanism that deterministically
computes the OSM Bundle Viewport from stable inputs.

## Viewport Roles

### OSM Bundle Viewport (data + cache identity)

Single Source of Truth for:

- `dist_m`
- Road Graph cache identity
- shared Feature Layer cache identity
- OSM query extent
- shared OSM bundle identity

### Renderer Viewport (visual only)

Responsible only for:

- clipping
- axis limits
- final crop
- poster composition

Renderer Viewport must never influence:

- `dist_m`
- cache keys
- OSM query extent
- shared bundle identity

## Why Cache Identity Is Not Derived From Renderer Viewport

Renderer Viewport serves visual composition goals (margins, crop, style-specific
layout). These values can change per style and may evolve over time. If cache
identity were derived from Renderer Viewport, style additions or layout
fine-tuning would cause unintended cache churn.

OSM Bundle Viewport is intentionally stable and policy-driven so cache identity
changes only when data-fetch scope changes by design.

## BundleViewportPolicy

Current minimal policy:

- `BundleViewportPolicy.NORMAL_MAP`

Future policies (for example `LARGE_MAP`, `LABEL_MAP`) should be added only
when there is a concrete requirement.

## Policy Version Contract

- `BUNDLE_VIEWPORT_POLICY_VERSION` is part of cache architecture.
- Policy constant changes are breaking changes.
- Breaking changes require intentional policy version bump.
- New style registration must not alter existing policy constants.

This guarantees that cache identity migration is explicit and intentional,
never accidental.

## Invariants

For every renderer call:

- `bundle_half_width >= renderer_half_width`
- `bundle_half_height >= renderer_half_height`

Equivalent set relation:

- `OSM Bundle Viewport ⊇ Renderer Viewport`

## Expected Behavior

For identical input:

- center latitude/longitude
- extent
- poster size
- bundle policy tier

all renderers must share the same:

- OSM Bundle Viewport
- `dist_m`
- Road Graph cache key
- shared Feature Layer cache keys

Renderer differences are limited to visual concerns only.
