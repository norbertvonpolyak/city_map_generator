# Universal Map Configurator (UMC) - Phase 1-2 Foundation

This folder contains the architecture and UI foundation for the Universal Map Configurator.

Scope delivered so far:
- React + TypeScript frontend foundation
- Shared TypeScript types for future map modules
- Module definitions for City Map, Building Map, and Star Map
- Premium split-layout shell with reusable configuration sections
- JSON-oriented interfaces for future poster configuration documents
- Interactive circular preview viewport with mock graphics
- Product visualization layer with module-specific SVG map placeholders
- Real City preview integration via FastAPI and existing generator SVG output
- Viewport engine (zoom, pan, reset)
- Reusable interactive object model (marker, heart, star, pin, text)
- Canvas-style interactions (place, drag, select, delete)
- Objects panel synchronized with viewport selection

Out of scope in this stage:
- Rendering logic
- API integration
- FastAPI endpoints
- Business logic implementation

## Directory Architecture

```text
configurator/
  README.md
  frontend/
    index.html
    package.json
    src/
      App.tsx
      index.css
      components/
        shell/
          ConfiguratorShell.tsx
        preview/
          InteractiveCircularViewport.tsx
          ObjectsPanel.tsx
        sections/
          ModuleSelectorSection.tsx
          LocationSection.tsx
          TemplateSection.tsx
          StyleSection.tsx
          ObjectsSection.tsx
      state/
        useConfiguratorState.ts
  shared/
    types/
      common.ts
      poster-config.ts
      interactive-preview.ts
      index.ts
    modules/
      types.ts
      city-map.module.ts
      building-map.module.ts
      star-map.module.ts
      definitions.ts
      index.ts
    schemas/
      interfaces.ts
      examples.ts
      index.ts
```

## Architecture Layers

1. shared/types
- Core domain types used by all modules.
- Includes module kind, section ids, and common configuration blocks.
- Defines module-specific config payloads with discriminated unions.

2. shared/modules
- Static module contracts and defaults.
- Exposes module metadata for UI composition and future registry logic.
- Includes one definition each for City, Building, and Star modules.

3. shared/schemas
- JSON document interfaces for future saved poster configuration payloads.
- Includes schema versioning and envelope patterns.
- Provides static examples for each module.

4. frontend/src/components
- Presentation-only UI shell and reusable sections.
- No backend communication or rendering pipeline integration.

5. frontend/src/state
- Single source of truth for configurator state and interactive preview state.
- Keeps module config, viewport transform, object list, placement tool, and selected object in one store.

## UI Foundation

The shell is a Globe Hero inspired split layout:
- Left: configuration panel containing reusable sections.
- Right: interactive preview workspace with circular masked viewport and object panel.

Reusable sections:
- Module Selector
- Location Section
- Template Section
- Style Section
- Objects Section

## Module Definitions

The phase-1 module contracts are static and typed:
- city-map
- building-map
- star-map

Each module definition includes:
- display metadata
- supported sections
- static default configuration
- status marker for foundation stage

## Interactive Preview Architecture (Phase 2)

Preview responsibilities are split into two reusable components:
- `InteractiveCircularViewport`: circular mask viewport, zoom/pan/reset controls, click-to-place, drag, selection, and keyboard delete support.
- `ObjectsPanel`: placement tool selector and synchronized object list with selection and deletion actions.

Product visualization mock layer:
- `ModuleMockMapLayer`: renders distinct SVG placeholder visuals for `city-map`, `building-map`, and `star-map` so UX can be tested before backend map generation integration.

Real city preview integration (Phase 4):
- `POST /preview/city` returns `{ "svg": "..." }` for the city preview.
- The frontend sends the current city text from the Location section and renders the returned SVG inside the circular viewport.
- City preview uses the existing generator preview path in minimal style only.
- Building and Star remain mock-only in this phase.

Interactive data contracts are shared in `shared/types/interactive-preview.ts`:
- `UMCPreviewObjectType`
- `UMCPreviewObject`
- `UMCPreviewViewportState`
- `UMCPreviewDocument`

State layer (`frontend/src/state/useConfiguratorState.ts`) stores:
- `previewViewport`
- `previewObjects`
- `selectedObjectId`
- `placementType`

This keeps the interactive preview JSON-ready for future export without depending on rendering or API layers.

## Future Poster Configuration Documents

The schema interfaces in shared/schemas define a JSON-friendly shape for later storage and transport:
- PosterConfigDocument
- PosterConfigEnvelope

Example envelopes for all three modules are included for reference and future integration.

## Running The Frontend

From configurator/frontend:

```bash
npm install
npm run dev
```

Build check:

```bash
npm run build
```

## Extension Points For Next Phase

1. Connect module state to backend APIs.
2. Bind viewport background and objects to generated map output.
3. Introduce validation rules and business logic.
4. Add export workflow and persistence.
5. Add iframe-focused integration hardening for WordPress embedding.

## Guardrails

- The production rendering engine under generator/ is untouched.
- No architectural changes were made to existing rendering code.
- All new phase-1 and phase-2 work lives under configurator/.
