# MapCanvas — Geofabrik/PBF Migration Plan (v2)

Status: **M0 — approved architecture, implementation not started.**
Scope of this document: planning only. No application code, dependency, test, or POC change is part of M0.

Legend used throughout:

- **[Verified]** — confirmed by reading the cited source.
- **[Recommendation]** — proposed design, not yet implemented.
- **[Unresolved]** — assumption or open question that must be settled before or during the cited milestone.

---

## 0. Binding implementation constraints

These constraints were set by the project owner and override any recommendation below.

1. The existing Overpass path remains the **default** and is kept **unchanged**.
2. OSMnx is **pinned to 2.0.7** and validated before any private OSMnx function is used. Explicit contract tests cover every private call (`osmnx.graph._create_graph`, `osmnx.features._create_gdf`).
3. Road-graph construction and feature assembly reuse the **existing OSMnx processing path** wherever feasible. Graph simplification and multipolygon semantics are **not reimplemented**.
4. Source-snapshot differences and Overpass element-selection differences are **documented limitations**. Pixel-identical output is never claimed.
5. The print-PDF retention fix is **out of scope** for the PBF migration and is tracked as a **separate required production task** (§9).
6. Work is incremental. Each milestone stops if its acceptance criteria fail, and the next milestone starts only after explicit approval.

### 0.1 Decisions recorded before M1 (2026-10-26)

- **Private OSMnx functions.** The OSMnx 2.0.7 private functions are used, with strict version and signature guards. An XML fallback is **not** introduced unless the private-function approach proves infeasible **and** it is separately approved.
- **`highway` list order.** The existing order, which can vary between runs, is preserved during the migration. Deterministic road styling is a future improvement (§15).
- **Pre-existing changes.** The five pre-existing modified files are preserved exactly. They are never staged, reverted, stashed, committed or edited by migration work.
- **PBF material outside Git.** `GEOFABRIK/` and all PBF files stay outside Git. Tests must work without a PBF, network access or AWS.
- **Test baseline (option A).** Tests characterize the **current working tree**, which differs from a clean `HEAD` checkout (§2.1). Tests that depend on working-tree-only behaviour carry the `working_tree` marker.
- **The Overpass fake is a fixture, not evidence.** The synthetic Overpass fake (`tests/support/overpass_fake.py`) is a test fixture for OSMnx processing, **not** proof of real Overpass selection behaviour. The way/relation selection rule remains an explicit migration risk (§7.1, §12).

---

## 1. Executive recommendation

**[Recommendation]**

- **Swap only the data-acquisition stage**, inside `_build_shared_osm_bundle` in `generator/core/osm_bundle_cache.py`, behind an environment-selected source:
  - `MAPCANVAS_OSM_SOURCE=overpass` is the default and leaves current behaviour unchanged;
  - `MAPCANVAS_OSM_SOURCE=pbf` selects the new local source.
- **One-time preprocessing.** The PBF source preprocesses a regional Geofabrik PBF into a local store containing:
  - raw, tag-filtered OSM elements (nodes, ways, relations, with tags, node references and relation members);
  - an R-tree of element bounding boxes.
- **Per request.**
  1. Select the elements Overpass would return, in Overpass's JSON response format, for the same OSMnx query box.
  2. Pass them to OSMnx 2.0.7's own client-side processing: graph creation, truncation, largest component, simplification, feature assembly and filtering.
- **What the engines receive.** The returned bundle dictionary is unchanged:
  - same keys and columns;
  - EPSG:4326 (latitude/longitude) data;
  - complete, uncut geometries.
- **What stays unchanged:** the engines, layouts, dispatcher, styles, sizes, viewport policy, rendering CRS behaviour and export.
- **Delivery:** local-only and reversible, as several independently testable changes. Nothing requires AWS.

---

## 2. Repository baseline (M0)

**[Verified]** Git state, inspected 2026-10-26 from `city_map_generator/` (the repository root):

- Branch `geofabrik-test`, HEAD `c6d0d7d` ("Decouple OSM Bundle Viewport from Renderer Viewport (#22)"), the same commit as `main` and `origin/main`.
- Uncommitted user modifications, unstaged, were preserved and not touched:

  | File | Change |
  |---|---|
  | `generator/core/osm_bundle_cache.py` | +38 / − lines (buildings-only layer selection) |
  | `generator/core/render_dispatcher.py` | +2 |
  | `generator/engines/render_building.py` | +132 / − |
  | `generator/engines/render_line.py` | +160 |
  | `render_manual.py` | +20 / − |
  | Total | 5 files, 315 insertions, 37 deletions |

- **Line numbers.** All line references in this document refer to the **current working tree**, including those uncommitted changes. They may shift once the changes are committed.
- **Location of PBF material.** The PBF file and POC scripts live in `GEOFABRIK/` at the **workspace root** (`C:\DEV\MapCanvas\GEOFABRIK`). That is outside this Git repository. Paths beginning `GEOFABRIK/` below are workspace-relative.
- **Location of OSMnx source.** OSMnx sources are cited from `.venv/Lib/site-packages/osmnx/` (installed version 2.0.7, matching `requirements.txt`).

### 2.1 Working-tree baseline vs clean `HEAD`

**[Verified]** from `git diff` of the five pre-existing changes:

- **Buildings-only mode.** In `generator/core/osm_bundle_cache.py`, a new `buildings_only_mode` parameter is passed through `_select_required_feature_layers`, `_load_or_build_feature_layers`, `_assemble_runtime_bundle`, `_build_shared_osm_bundle` and `load_or_build_shared_osm_bundle`. Buildings-only requests ask for the `buildings` layer only. **This does not exist at `HEAD`.**
- **Buildings-layer tags.** `_FEATURE_TAGS_BUILDINGS` differs from `HEAD`:
  - **Added:** `landuse=harbour`, `natural=shingle`, `man_made=pier|breakwater`, `amenity=marina`.
  - **Removed:**
    - `natural=bay|strait|tree|coastline|island`;
    - `water=*`, `waterway=*`, `railway=*`;
    - `amenity=school|college|university`;
    - `place=island|islet`;
    - `highway=footway|path|track|steps`.
  - **Consequence:** the buildings-layer cache hash (`qh…`) differs from `HEAD`.
- **Dispatcher.** `generator/core/render_dispatcher.py` gained a `buildings_only` argument, passed to the Building engine.
- **What the PBF path follows.** The PBF path reuses whatever `_FEATURE_LAYER_SPECS` contains, so it follows the working tree.
- **What this means for tests.** Tests marked `working_tree` (`buildings_only_mode`, the `man_made` tag) are **not** expected to pass on a clean `HEAD` checkout. All other M1 tests use only behaviour also present at `HEAD`.

---

## 3. Verified current architecture

### 3.1 Entry points

- **Manual render.** `render_manual.py` `main()`:
  - uses fixed `LAT`/`LON` and `spec_from_size_key(..., dpi=150)`;
  - calls `render_product(preview_mode=False, order_id="MANUAL")`;
  - resizes the PNG to a WebP;
  - **deletes the PNG/SVG/PDF** (around L212–L221).
- **CLI.** `main.py` (L71–L120) calls `render_product(..., order_id="DESIGN_TEST")`. It parses `--seed` and `--font-path` but does not pass them on.
- **API.**
  - `api.py` `/preview/city` → `service.generate_city_preview_svg`, which geocodes with `ox.geocode` (`service.py` L39–L47) and renders with `preview_mode=True` (L94–L105).
  - `/preview` → `service.generate_preview`, which receives coordinates directly.
- **Batch.**
  - `batch_render_all.py` (L101–L127) and `batch_render_from_config.py` (L114–L133) prewarm the cache by calling `load_or_build_shared_osm_bundle` directly, then render through a `main.py` subprocess.
  - `batch_render_budapest_webp.py` calls `render_product` in-process.

**Geocoding stays separate.** City geocoding is only used in `service.py`. Feature acquisition always receives explicit coordinates.

### 3.2 Viewports and `EXTENT_M`

**[Verified]**

- **Definition.** `EXTENT_M` (`E`) is the **renderer viewport's projected half-height in metres**.
- **Map box size.** `build_poster_layout` (`generator/layouts/layout_utils.py` L174–L250) computes the visible map box after style-specific margins:
  - `side = 0.04 · min(W, H)` by default;
  - bottom margin = `0.10 · H`, uniform, a style-specific ratio, or the `vintage_atlas` multiplier.
- **Renderer half-sizes.** `PosterLayout.map_viewport_half_sizes_m` (L77–L80):
  - `half_height_m = E`
  - `half_width_m = E · Wv / Hv`, where `Wv`, `Hv` are the map-box width and height in cm.
  - Full projected coverage is therefore `2E` high and `2E·Wv/Hv` wide. `EXTENT_M` is neither a radius nor the total width.
- **Bundle viewport.** `generator/core/bundle_viewport_policy.py` L20–L46 (`NORMAL_MAP` policy) is style-independent:
  - fixed margins: 4 % sides and top, 10 % bottom;
  - same `half_height = E`;
  - `half_width = E · Wb / Hb`.
- **Containment check.** `generator/core/render_dispatcher.py` L126–L134 raises an error unless `bundle_half_* >= viewport_half_*`.

### 3.3 Data acquisition (Overpass path)

**[Verified]**, `generator/core/osm_bundle_cache.py`:

- **Single choke point.**
  - `_build_shared_osm_bundle` (~L1059–L1119) computes `dist_m = ceil(sqrt(bhw² + bhh²)) + 300` (metres, L1074).
  - It then calls `_load_or_build_road_graph`, which runs `ox.graph_from_point(..., dist=dist_m, custom_filter=_ROAD_CUSTOM_FILTER, simplify=True)` (L44–L48, ~L762–L820).
  - Then `ox.graph_to_gdfs(graph, nodes=False, edges=True)` (L1089).
  - Then `_load_or_build_feature_layers` / `_load_or_build_feature_layer`, which call `ox.features_from_point(..., tags, dist=dist_m)`.
  - Finally `_assemble_runtime_bundle` (~L935–L958).
- **Layer specs and tags:** `_FEATURE_TAGS_BUILDINGS` and `_FEATURE_LAYER_SPECS` (L62–L169).
- **Layer selection by mode** (`_select_required_feature_layers`):

  | Mode | Layers requested |
  |---|---|
  | buildings-only | `["buildings"]` |
  | `include_building_features=True` | `buildings`, `trees`, `waterway`, `railway`, `paths`, `water`, `green`, `coast`, `islands` |
  | otherwise | `water`, `green`, `coast`, `islands` |

- **Public entry point.** `load_or_build_shared_osm_bundle` ignores `extent_m` (it is kept only for API compatibility).
- **Cache.** Pickle files keyed by centre (6 decimals), `dist_m`, tag hash and version (`_build_road_graph_cache_filename`, `_build_feature_layer_cache_filename`). The road graph may be reused from a larger cached distance (`_find_best_road_graph_superset`). **The cache key has no source identifier.**
- **Overpass resilience.** Endpoint rotation and retry are in `_run_with_overpass_fallback`.

### 3.4 OSMnx query box

**[Verified]**, OSMnx 2.0.7:

- `utils_geo.bbox_from_point` (`utils_geo.py` L371–L408) uses `R = 6 371 009 m`:
  - `Δlat = degrees(dist / R)`
  - `Δlon = Δlat / cos(radians(lat))`
  - `bbox = (lon − Δlon, lat − Δlat, lon + Δlon, lat + Δlat)`
- `graph_from_point` (`graph.py` L119–L205) and `features_from_point` (`features.py` L133–L175) both use this function, with `dist_type="bbox"`.
- This box is a spherical latitude/longitude approximation, **not** the projected renderer rectangle.

### 3.5 Engines and the bundle they consume

**[Verified]**

| Engine | Bundle call | Keys consumed | Columns read |
|---|---|---|---|
| Block (`render_block.py` ~L361) | `include_building_features=False` (default) | `edges_raw`, `water_raw`, `coast_raw`, `islands_raw` | `highway` (`str(list)` → `minor`) |
| Building (`render_building.py` ~L456) | `include_building_features=not buildings_only`, `buildings_only_mode=buildings_only` | `edges_raw`, `gdf_all_raw`, `trees_raw`, `waterway_raw`, `railway_raw`, `paths_raw`, `islands_raw`, `coast_raw` | `highway` (first list element), `bridge`, `building`, `building:part`, `landuse`, `leisure`, `natural`, `amenity`, `place`, `highway`, `man_made`, `waterway` |
| Line (`render_line.py` ~L344) | `include_building_features=True` | `edges_raw`, `water_raw`, `green_raw`, `gdf_all_raw`, `coast_raw` | `highway` (first list element), `bridge`, `landuse`, `amenity`, `natural`, `man_made` |

- **No engine uses the graph structure.** Only the edge table's columns and geometry are read.- **Stale helper.** `_bundle_usage_sets()` in `osm_bundle_cache.py` is out of date: it omits `islands_raw` for Building and `gdf_all_raw`/`coast_raw` for Line. Tests do not rely on it.- **Projection.** Every engine projects the centre point and each layer separately with `ox.projection.project_gdf`, which picks an automatic UTM zone (`projection.py` L117–L133). The engines then clip to a projected rectangle with `gpd.clip`.

### 3.6 Composition and export

**[Verified]**

- **Map layer.** The engine writes a map-only SVG to a temporary directory.
- **Poster SVG.** `compose_poster_outputs` (`layout_utils.py` ~L1504–L1561) writes a poster SVG whose size is set in cm; the map is nested inside it with `overflow="hidden"`.
- **PNG.**
  - `svg_to_png` uses `renderPM` at 96 DPI, then CairoSVG (sized in drawing units), then PyMuPDF at 96 DPI, depending on which backend works.
  - A special branch (`center_title` and `bottom_fade`) instead renders a PDF and rasterizes it with PyMuPDF at 96 DPI.
- **PDF** (`_svg_to_pdf_bytes`, ~L1469–L1491): CairoSVG when available and preferred, otherwise svglib/ReportLab.
  - Non-Line styles export a PDF only when `preview_mode=False`.
  - The Line dispatcher always writes a PDF with `prefer_cairo=False`, plus a WebP capped at 350 KiB.

---

## 4. Existing PBF proof-of-concept assessment

**[Verified]** All four POCs read `GEOFABRIK/hungary-260918.osm.pbf`, falling back to `hungary-latest.osm.pbf`. They select a fixed Budapest box `(19.00, 47.46, 19.10, 47.54)`, stream ways and areas with pyosmium (`with_locations()`, `with_areas()`), and **intersect geometries with the box in EPSG:4326 before projection**.

| POC | Extracted features | Production code reused | Bypassed / replaced | Engines | Comparable to production? |
|---|---|---|---|---|---|
| `validate_pbf.py` | Object counts; highway/railway/waterway/boundary ways; building/water/green/admin areas | None | Everything; own EPSG:3857 renderer | None | No |
| `poc_falamra_svg.py` | Roads, buildings, water, green, railways | Only the `BuildingStyleConfig`/`RoadStyle` dataclass shapes | Everything; own EPSG:3857 renderer | None | No |
| `poc_urban_modern_geofabrik.py` | Any `highway=*` way; water areas | `render_map_block` (via a monkeypatched loader) | Road filter, OSMnx graph semantics, coast/islands (empty), cache; viewport derived from the box, not from `EXTENT_M` and the layout | Block (map layer only) | Partially |
| `poc_urban_modern_full_poster.py` | Same as above | `render_product` → `render_map_block` → poster composition, in `preview_mode=True`, `50x70` | Same as above | Block (full poster) | Partially |

**Gaps common to all POCs:**

- They do not use the production tag filters, `_ROAD_CUSTOM_FILTER` or OSMnx's polygon-versus-line rules.
- Their geometries are cut, not whole.
- They do not use the `dist_m` query box.
- They have no Building or Line support.
- They have no cache identity.

---

## 5. Proposed data-source interface

**[Recommendation]** The contract **is** the existing bundle dictionary. No new framework is introduced.

- **Selection point.** Choose the source inside `_build_shared_osm_bundle`:
  - `overpass` (the default) runs the existing code exactly as it is today;
  - `pbf` calls the new module `generator/core/pbf_source.py`.
- **Conceptual signature of the new module:**
  - `load_pbf_road_edges(center_lat, center_lon, dist_m, store) -> GeoDataFrame` (the same shape as `ox.graph_to_gdfs(..., nodes=False)`);
  - `load_pbf_feature_layer(layer_name, center_lat, center_lon, dist_m, store) -> GeoDataFrame | None`, using the tags from `_FEATURE_LAYER_SPECS`.
- **Configuration:** `MAPCANVAS_OSM_SOURCE`, `MAPCANVAS_PBF_STORE_DIR`, `MAPCANVAS_PBF_PATH`. Credentials are never stored in code.
- **Reused unchanged:** `_select_required_feature_layers` and `_assemble_runtime_bundle`. These remain the adapters that turn layers into the per-engine bundle.
- **Cache.**
  - PBF bundles reuse the existing pickle cache, with a `src-pbf_<manifest-hash>` token added to the filenames.
  - Overpass cache filenames do not change.
- **Coverage guard.** If the query box is not fully inside the PBF header's bounds, raise a clear error. For example, the current manual default (Denpasar) is not covered by the Hungary PBF.

---

## 6. Road graph parity

### 6.1 Current OSMnx semantics

**[Verified]**, `graph_from_polygon` in `graph.py` L409–L516:

1. Query box from `dist_m` (§3.4). It is projected to UTM, **buffered by 500 m**, and projected back to latitude/longitude (`poly_buff`).
2. Overpass query `way[<custom_filter>](poly:poly_buff); >; out;` (`_overpass.py` L357–L404).
   - The filter is `["highway"~"motorway|…|steps"]`, an **unanchored, case-sensitive regex**. So `service` also matches `services`, and multi-value tags such as `footway;steps` match too.
   - No access filter is applied when a custom filter is used.
3. `_create_graph` (`graph.py` L752–L860):
   - edges keep only the tags in `settings.useful_tags_way` (`settings.py` L168–L184): `access`, `area`, `bridge`, `est_width`, `highway`, `junction`, `landuse`, `lanes`, `maxspeed`, `name`, `oneway`, `ref`, `service`, `tunnel`, `width`;
   - `oneway` becomes a boolean, and `-1`/`reverse` reverse the node order;
   - non-oneway ways are added in **both directions** (`reversed=True` for the second copy), because the network is not bidirectional (`bidirectional_network_types=["walk"]`);
   - edge lengths are added.
4. `truncate_graph_polygon(G, poly_buff)` keeps only nodes inside the polygon; edges are removed with their nodes (`truncate.py` L99–L160). Then `largest_component(strongly=False)` keeps the largest weakly connected component.
5. `simplify_graph` (`simplification.py` L276–L420) removes interstitial nodes and isolated rings.
   - Merged edges keep **one value if all segments agree, otherwise `list(set(values))`**. Segments missing a tag contribute nothing.
6. `truncate_graph_polygon(G, polygon)`, without the buffer, then `largest_component` again.
7. `graph_to_gdfs` (`convert.py` L173–L192) fills straight two-point line geometries for unsimplified edges. The index is `(u, v, key)` and the CRS is EPSG:4326.

### 6.2 How the PBF path reproduces it

| Step | Mechanism | Parity |
|---|---|---|
| 1 query box and `poly_buff` | `ox.utils_geo.bbox_from_point`, `ox.utils_geo.bbox_to_poly`, `ox.projection.project_geometry` + `buffer(500)` | Exact (same functions) |
| 2 element selection | Ways where `re.search(<same pattern>, highway)` matches and whose bounding box intersects `poly_buff`, plus all of their nodes | Superset; see below |
| 3 graph build | `osmnx.graph._create_graph(response_jsons, bidirectional=False)` | Exact (same code; private, version-guarded) |
| 4–6 truncate, largest component, simplify, truncate, largest component | Public `ox.truncate.truncate_graph_polygon`, `ox.truncate.largest_component`, `ox.simplification.simplify_graph`, in the order of `graph.py` L495–L522 | Exact (same code) |
| 7 table conversion | `ox.graph_to_gdfs(G, nodes=False, edges=True)` | Exact |

**Why a superset is safe for roads.** A way that the bounding-box query selects but Overpass does not has no node inside `poly_buff`, so step 4 removes it before the connected-component and simplification steps. The graph result therefore does not depend on Overpass's exact way-selection rule, provided the source data is the same.

**Resulting values**, identical to production given the same data:

- `highway` is a `str` for single-way edges and a `list` for merged edges whose ways disagree.
- `bridge` is NaN unless at least one merged segment has it. A bridge segment merged with plain road gives the **whole** simplified edge `bridge="yes"`. This is existing production behaviour.
- Two-way roads appear twice (both directions); the engines draw both. This is existing behaviour.

**Characterized in M1** (`tests/test_osmnx_reference_semantics.py`):

- **Edges that run past the query box are dropped.** Simplification runs **before** the final truncation to the query box. A simplified edge whose far endpoint lies outside the box is therefore removed **entirely**, including all of its interior segments that lie inside the box. It is not cut back to its last node inside the box.
- **Why the map is still covered.** The renderer viewport stays covered because the query box exceeds it by at least about 500 m (B3, §8). Long simplified edges near the box edge are still dropped.
- **The PBF path inherits this.** Because it runs the same OSMnx code, the PBF path behaves the same way.

**Fallback.** A temporary OSM XML file read with the public `ox.graph_from_xml(simplify=False, retain_all=True)` (`graph.py` L534–L583) remains a documented alternative only. It is **not** implemented unless the private-function approach proves infeasible and the fallback is separately approved (§0.1). The M1 equivalence tests show the private-function approach works with OSMnx 2.0.7.

### 6.3 Not reproducible, or limitations (documented, per constraint 4)

- **Source snapshot.** The Geofabrik extract date and live Overpass data differ.
- **Non-determinism already present on the Overpass path.** `list(set(...))` ordering changes between Python processes because string hashing is randomised. Building and Line style roads by the **first** list element (`render_building.py` L44–L45, `render_line.py` L39–L40); Block classifies the list as `minor` (`render_block.py` L47–L63).
  - Parity tests set `PYTHONHASHSEED=0` and compare `highway` lists as sets.
  - **Decision:** this behaviour is **preserved** during the migration. Making road styling deterministic is a future improvement (§15), because it changes the visual output.
- **Element ordering.** When duplicate ways connect the same nodes, simplification keeps the first; connected-component ties also depend on order. The PBF path sorts elements by ID, but it cannot match Overpass's response order.
- **Regional border.** Ways cut off at the edge of the Geofabrik extract. Missing node references are counted during preprocessing.
- **Road-graph cache reuse from a larger distance** (`_find_best_road_graph_superset`) already returns results that differ from an exact-distance fetch. It is kept as it is, separately for each source.

---

## 7. Feature geometry contract

**[Recommendation]**, using the **[Verified]** OSMnx semantics cited below.

- **What the store holds:** raw elements only.
  - nodes: ID, latitude/longitude, tags;
  - ways: ID, tags, ordered node references;
  - relations: ID, tags, members with their roles;
  - per-layer membership flags.
  - **No clipped or pre-assembled geometries are stored.**
- **How membership flags are computed:**
  - **Tag matching.** Same semantics as OSMnx: `True` means the key is present; `str`/`list` means an exact value match.
  - **Key-only matches.** Elements that match only on the **key** are also flagged, because `_process_features` matches on keys first and only filters by value later (`features.py` L470–L505).
  - **Completeness.** Member ways of matching relations, and every referenced node, are always included.
- **Assembly is OSMnx's own code.** The adapter calls `osmnx.features._create_gdf(response_jsons, polygon, tags)` (`features.py` L381–L427), which applies:
  - **Closed ways.** They become polygons according to `_POLYGON_FEATURES`; `area=no` keeps them as lines (`features.py` L513–L563).
  - **Relations.** Only `multipolygon` and `boundary` relations are handled:
    - outer and inner rings are joined with `linemerge`/`polygonize`;
    - an inner ring is subtracted only if an outer ring fully contains it;
    - a missing member way turns the relation into an empty Polygon, which is then dropped (`features.py` L566–L673).
  - **Final filter.** `_filter_features` repairs geometries with `make_valid`, keeps features that intersect the query box, and filters by tag value. If nothing matches, it raises `InsufficientResponseError` (`features.py` L676–L734).
  - **No osmium area assembly.** pyosmium's own polygon assembly is **not** used, because it builds geometries differently from OSMnx.
- **Complete, uncut geometry.** Overpass's `(._;>;)` recursion returns every node of a way and every member of a relation, including those outside the query box. The PBF path does the same by recursively adding members and nodes from the store.
- **Spatial query.** An R-tree of element bounding boxes returns candidate elements, then recursion and the OSMnx filter trim the result to the final set.
- **Missing layers.** Coast and islands are handled exactly as today (`osm_bundle_cache.py` `_load_or_build_feature_layer`, the `InsufficientResponseError` branch), because the same exception type is raised.
- **Engine geometry filters stay unchanged**, because the engines receive the same EPSG:4326 tables with the same columns. These include:
  - Block: 300-unit area filter, 5 m buffer, polygonization;
  - Building: 15 m² minimum area, hole filling, water masking;
  - Line: geometry-type filters.

### 7.1 Overpass element-selection limitation

**[Unresolved]**, documented per constraint 4.

- **What differs.** Overpass selects elements on its server with `(poly:…)` (`_overpass.py` L286–L354). A feature that **fully surrounds** the query box (lake, forest, large multipolygon) without any node, segment or member inside it is probably **not** returned by Overpass today. A bounding-box superset plus `_filter_features` would keep it.
- **Default PBF mode ("Overpass-compatible").** Keep a way only if one of its segments intersects the query box. Keep a relation only if one of its member ways qualifies or one of its member nodes lies inside.
- **Open point.** It is not known whether Overpass's rule for ways is "a segment intersects" or "a node is inside". Settling it needs an opt-in live probe or authoritative Overpass documentation.
- **Test fixture, not evidence.** The M1 fake (`tests/support/overpass_fake.py`) implements the "segment intersects" rule as an **assumption**. It is used only to feed OSMnx's processing. Tests that pass against it do **not** verify real Overpass behaviour. `test_enclosing_polygon_depends_on_overpass_selection` documents both possible outcomes.
- **Later option.** A "complete areas" mode, which would include the enclosing features, is a later product decision because it changes the visual output.

---

## 8. CRS, viewport, clipping, and bounds tests

**[Recommendation]**

- **Query box.** The PBF source calls `ox.utils_geo.bbox_from_point((lat, lon), dist_m)` directly; it does not reimplement it. `dist_m` comes from the unchanged formula. The centre is passed unrounded; only cache filenames use 6 decimals.
- **Rendering CRS is unchanged.**
  - The PBF output is EPSG:4326, so every engine's `ox.projection.project_gdf` UTM selection behaves as it does today.
  - The existing risk that layers are projected separately near a UTM zone boundary is **documented, not changed**.
  - Fixing the projection to one explicit CRS would be a separate, later change with its own framing regression tests.
- **Tests:**
  - **B1, same query box:** for a grid of centres (Budapest, ±60° latitude, a UTM zone boundary) and distances, the query box is float-identical between the Overpass-path call and the PBF-path call.
  - **B2, extent contract:** for all 11 styles × 7 size keys × `EXTENT_M` ∈ {1000, 2000, 5000}:
    - renderer half-sizes equal `E·Wv/Hv` from the layout's map box;
    - the bundle viewport contains the renderer viewport;
    - `dist_m` equals the formula.
  - **B3, coverage:** project the four corners of the projected renderer viewport back to EPSG:4326 and assert they lie inside the query box. Report the remaining margin, and fail if any style, size, extent or latitude combination leaves none.
    - **M1 result:** passed for all 11 styles × 7 sizes × 3 extents at 7 locations: 0°, 47.5°N, 45°S, 60°N, 65°N, and both sides of a UTM zone boundary.
    - The smallest margin is about 496 m (`architect_sage`, `60x90`, `E=1000`, at the UTM zone boundary). It is about 503 m at 65°N.
    - The viewport-edge samples are taken every 50 m. Distances are measured on the spherical approximation (R = 6 371 009 m).
  - **B4, boundary-crossing features, synthetic, offline:** fixtures with a feature crossing each viewport edge and corner, an enclosing polygon, a multipolygon with a hole and an outer ring partly outside, a road whose endpoint is just outside the query box, and a bridge segment.
    - **Reference:** the real `ox.graph_from_point` / `ox.features_from_point`, with `osmnx._overpass._download_overpass_network` and `_download_overpass_features` patched to return the synthetic, Overpass-selected elements.
    - **Check:** compare with the PBF path built from the same fixture: edge `(u, v, key)` and feature IDs, geometry equality, `highway` as a set, and `bridge`.
  - **B5, real data, Budapest:** independently scan the Hungary PBF with osmium to list, for each layer, the IDs of features intersecting the renderer viewport. Assert they are all present in the PBF bundle, and report any extras.

---

## 9. Separate required production task: print-PDF retention

**[Verified] / out of scope for the migration (constraint 5)**

- **Current behaviour:**
  - `render_manual.py` deletes the PDF after generating the WebP (around L212).
  - The API preview runs with `preview_mode=True` and never exports a PDF (`service.py` L94–L105, `render_dispatcher.py` around L381).
  - The batch scripts delete their intermediate files.
- **Existing print path:** `render_product(preview_mode=False, order_id=...)`.
- **Where to fix it later:**
  - a new order/print function in `service.py`, next to `generate_city_preview_svg`, for the webshop;
  - or a keep-the-PDF option in `render_manual.py`.
  - Dispatcher and layout code stay unchanged.
- **Acceptance criteria:**
  - for each order, the PDF is kept at a deterministic location keyed by order;
  - page size equals `cm × 72 / 2.54` points, within ±0.01 pt;
  - PyMuPDF finds vector drawings in the map area, and no single raster image covers the map box, except texture layers that are explicitly allowed;
  - generating the preview neither changes nor deletes the PDF (its checksum is the same before and after).

---

## 10. Test strategy

| Category | What it shows | What it does **not** show |
|---|---|---|
| T1 Data-source contract | Same bundle keys, columns, geometry types, CRS and missing-layer handling; OSMnx version guard; contract tests for `_create_graph` and `_create_gdf` | Correct geography |
| T2 Geographic correctness | B1–B5: query box, coverage, boundary crossings, ring/hole assembly, graph equality on synthetic data | Matching real data |
| T3 Rendering success | Every engine renders all 11 styles × 7 sizes × several extents from PBF data without errors | Appearance |
| T4 Visual comparison (opt-in, needs network) | PBF vs Overpass at the same centre, measured by per-layer feature counts, total road length, building area and image difference | **Pixel-identical output is not expected** (snapshot, element order, existing list non-determinism) |
| T5 PDF vector preservation | Page size, vector drawing count, no full-map raster image (tracks §9) | Data-source parity |
| T6 Preview output | PNG/WebP dimensions, 1500 px longest side, compression limit, and the PDF is untouched | Print quality |

All categories except T4 run offline with no AWS access, using synthetic fixtures and the existing Hungary PBF.

---

## 11. Milestones

Each milestone is a separate change. It stops if its acceptance criteria fail, and the next milestone needs explicit approval. Overpass stays the default throughout.

| # | Objective | Files | Acceptance | Rollback |
|---|---|---|---|---|
| M0 | Baseline and plan document | `docs/GEOFABRIK_MIGRATION_PLAN.md` only | Git state reported; no other file changed | Delete the document |
| M1 | Test harness and offline OSMnx reference | New `pytest.ini`, `requirements-dev.txt` (`pytest>=8.4`), `tests/` (§11.1); this document | T1 baseline on the Overpass contract, B1–B3 and the B4 harness pass offline; private-function equivalence passes; the five pre-existing diffs unchanged; production `cache/` and `output/` untouched | Delete `tests/`, `pytest.ini` and `requirements-dev.txt`, and undo the M1 edits to this document |
| M2 | Preprocessing store | New `generator/core/pbf_source.py` + store-building CLI; `osmium` added to `requirements.txt` | Store builds from the Hungary PBF; manifest (PBF size, modification time, sha256, PBF header timestamp/bounds, tag-rule hash, schema version, OSMnx version) written; missing references counted; store rebuilt when the manifest changes | Delete the store directory; revert |
| M3 | Query and OSMnx processing adapter | `pbf_source.py` | OSMnx 2.0.7 guard and private-call contract tests pass; B4 shows exact equality on synthetic fixtures; no production wiring yet | Revert |

> **M3 status (2026-10-26): delivered, see §11.4.** All three engines (11 registered styles + the working-tree buildings-only mode) render from the local store via an in-memory loader swap; no production module changed or imports the adapter. M4 is **not** approved.
>
> **M4 status (2026-10-27): delivered on explicit approval despite the blocked M6 comparison, see §11.6.** PBF is opt-in via `MAPCANVAS_OSM_SOURCE=pbf`; Overpass stays the default. M5–M9 are not started.
| M4 | Integration behind the environment setting | `generator/core/osm_bundle_cache.py` (source switch, cache token) | With the variable unset: Overpass behaviour and cache filenames byte-identical. With `pbf`: Budapest bundles pass T1 and B5; out-of-coverage error works | Unset the environment variable or revert |
| M5 | Rendering validation | None (tests only) | T3 passes; output dimensions unchanged | Environment variable |
| M6 | Comparison against Overpass | None | T4 run once; differences measured and explained; no claim of identical maps | Nothing to roll back |
| M7 | Output checks | Tests only | T5 and T6 thresholds recorded (§9 tracked separately) | Nothing to roll back |
| M8 | Benchmarks | None | Store build time and size, per-layer query time and peak memory recorded (measurements only) | Nothing to roll back |
| M9 | S3 and regional-data design | Documentation only | §13 approved | Nothing to roll back |

### 11.1 M1 test harness

- **Configuration.**
  - `pytest.ini`: `testpaths=tests`, `pythonpath=.`, `-p no:cacheprovider`, and the `working_tree` marker.
  - `requirements-dev.txt`: pytest only.
- **Isolation (`tests/conftest.py`), applied to every test:**
  - network blocked (`requests.Session.request` raises);
  - OSMnx HTTP cache disabled;
  - `overpass_url` restored after each test;
  - bundle cache redirected to a temporary folder;
  - `OVERPASS_DEBUG` and `OSM_OVERPASS_ENDPOINTS` cleared.
- **Test modules:**
  - `tests/test_osmnx_contract.py`: version, private-function signatures, and private-function equivalence (graph, plus every layer in `_FEATURE_LAYER_SPECS`).
  - `tests/test_osmnx_reference_semantics.py`: B4 characterization.
  - `tests/test_viewport_contract.py`: B2, all 11 styles × 7 sizes × 3 extents.
  - `tests/test_query_envelope.py`: B1 on the Overpass side, plus B3 coverage at 7 locations.
  - `tests/test_bundle_contract.py`: T1. The `working_tree` tests live here.
- **Run:** `.venv\Scripts\python.exe -m pytest` in `city_map_generator/`.
  - The clean-`HEAD`-compatible subset is `-m "not working_tree"`.
  - No PBF-dependent tests exist yet. The "skip when the PBF is missing" fixture arrives with M2.

### 11.2 M2 as delivered and S4 measured results (2026-10-26)

M2 deviated from the table above in two places:

- The module is `generator/core/pbf_store.py`, not `pbf_source.py`. It contains the store build, the reader and a CLI (`build`/`inspect`/`bench`). No production module imports it.
- `osmium==4.3.1` is declared in a separate `requirements-pbf.txt`. `requirements.txt` is unchanged.

Offline tests live in `tests/pbf_store/`. The real-PBF tests are opt-in: `MAPCANVAS_PBF_INTEGRATION=1`, and for the full build also `MAPCANVAS_PBF_FULL_BUILD=1` and `MAPCANVAS_PBF_STORE_DIR`.

**Source**

- File: `GEOFABRIK/hungary-260918.osm.pbf`, 324,974,324 B.
- sha256 `dc2c1dae…cbf2eb2`.
- Header bbox 16.108446, 45.732067, 22.906494, 48.589212.
- Replication timestamp 2026-09-18T20:21:10Z (sequence 4914); generator osmium/1.16.0.

**S4 full build**

- Store location: `%LOCALAPPDATA%\MapCanvas\pbf_store\osm_store.sqlite`.
- Machine: i7-13850HX, 31.6 GB RAM.

| Metric | Value |
|---|---|
| Wall time | 1,907 s (pass A 183 s, pass B 864 s, index/finalize 856 s) |
| Peak working set | 3.04 GB |
| Store size | 2.40 GB (single file; no lock or temp files left) |
| Nodes / ways / relations | 34,008,084 / 5,564,906 / 79,016 |
| Road ways / layer ways / member-only ways | 737,629 / 4,705,733 / 335,733 |
| Missing node refs / ways without location | 0 / 0 |
| Relations with missing members | 8 (115 member refs; extract-border truncation) |
| Nested relation refs | 8 |
| Relations without bbox | 0 |
| `tag_rules_hash` | `8b837899…4b752627` |

**Integrity checks**

- `status=complete`; opening with sha256 verification takes 0.42 s.
- The real-PBF header test passes.
- The full-build test was deliberately skipped. The S4 driver performed the identical build, and running the test would have duplicated a ~32-minute build.
- Diagnostic query boxes at d=1522 and d=6563 m returned 0 missing nodes and 0 missing members. Locations: Budapest, Sopron (AT border) and Szeged (RS/RO border).

**Lookup benchmark** (`bench`, 5 repeats, median / p95)

| Location | Query distance | Candidate lookup | Element fetch | Ways / relations / nodes |
|---|---|---|---|---|
| Budapest | 4,058 m (E=3000, 50x70) | 0.363 / 0.382 s | 1.958 / 2.148 s | 81,973 / 3,748 / 462,992 |
| Budapest | 6,563 m | 0.668 / 0.767 s | 4.099 / 4.618 s | 170,702 / 4,289 / 939,643 |
| Sopron (border) | 6,563 m | 0.099 / 0.109 s | 0.677 / 0.707 s | 33,153 / 220 / 216,003 |

**Test suite after the build and render:** 550 passed, 2 skipped. This is unchanged from the result after M2.

### 11.3 Acceptance render from the local store (PoC, not M3/M4)

**Adapter.** `C:\DEV\MapCanvas\pbf_poc_render\render_budapest_from_pbf_store.py` is standalone and outside Git. It swaps `load_or_build_shared_osm_bundle` in memory for the Block engine only:

- Roads: `_create_graph`, then truncate, largest component and simplify, as in `graph_from_polygon`.
- Features: an assumed segment-intersect selection, then `_create_gdf`.
- The bundle is then assembled by the production `_assemble_runtime_bundle`.
- It calls the unchanged `render_dispatcher.render_product(preview_mode=False, use_cache=False)`.
- It does not change production modules, the cache or `output/`.

**Render parameters**

- Budapest, 47.4979, 19.0402.
- `EXTENT_M=3000`, `50x70`, `urban_modern` (Block engine), 300 dpi spec.
- Viewport half-size 2262.3 × 3000 m; `dist_m=4058`.

**Bundle**

| Item | Value |
|---|---|
| Road candidate ways | 38,533 |
| Ways dropped for missing nodes | 0 |
| Graph nodes / `edges_raw` | 126,261 / 95,034 |
| Water features | 90 |
| Green features | 2,666 |
| Islands | 3 |
| Coast | 0 (no coastline in the box, as expected) |
| Incomplete ways or relations | 0 in every layer |

**Runtime:** 78.3 s total. Store open + sha256 0.5 s; roads 23.4 s; four feature layers 16.1 s; `render_product` 73.5 s, which includes the composition and export.

**Outputs** (`C:\DEV\MapCanvas\pbf_poc_render\budapest_urban_modern_3000m_50x70_20261026_224136\`)

| File | Details |
|---|---|
| PDF | 1,232,256 B. One page of 1417.32 × 1984.25 pt (50.0 × 70.0 cm); vector only (26,906 drawings, no raster images); title as outlines |
| PNG | 1890 × 2646 px |
| SVG | 6.8 MB |
| WebP preview | 1071 × 1500 px, 144 KB |
| `run_log.json` | Parameters, PBF identity, timings and counts |

**Visual inspection of the PNG and WebP:**

- Present: the Danube with Margaret Island, the central bridges, the Buda hill road network, the Pest grid with the boulevards, and the lake at Feneketlen-tó.
- Not found: blank regions, clipping at the frame, broken polygons or style regressions.
- Not yet done: no pixel comparison against an Overpass render (that is M6). Differences from Overpass selection and from the snapshot are expected (§7.1).

**Safeguards after the render (verified against the S4 baseline)**

- Git status is identical to the baseline.
- The diff of the five pre-existing modified files has the same hash, `7D5598…CE7`.
- `requirements.txt` hash is unchanged.
- `cache/` and `output/`: all 121 files identical.
- `GEOFABRIK/`: all 16 files identical.
- The 19 M1/M2 file hashes are unchanged.

### 11.4 M3 isolated PBF bundle source (2026-10-26)

**Scope.** M3 is approved. M4 (production wiring, source selection) is **not** approved and not started.

- New code: `generator/core/pbf_source.py`. No production module imports it, and a test enforces this.
- Production renderer, Overpass loader, `requirements.txt` and the five pre-existing modified files are unchanged.

#### 11.4.1 Engine data contract (verified before implementation)

All three engines call `load_or_build_shared_osm_bundle` by name (imported into each engine module). Each loads layers through `_select_required_feature_layers`. All engines read only edge columns and geometry, never graph topology (§3.5).

| Engine (styles) | Loader keywords | Layers built | Keys actually read |
|---|---|---|---|
| Block (`urban_modern`, `midnight_ember`) | none (`include_building_features=False`) | roads + `water`, `green`, `coast`, `islands` | `edges_raw`, `water_raw`, `coast_raw`, `islands_raw` |
| Building (7 styles) | `include_building_features=True`, `buildings_only_mode=False` | roads + all 9 layers | `edges_raw`, `gdf_all_raw`, `trees_raw`, `waterway_raw`, `railway_raw`, `paths_raw`, `islands_raw`, `coast_raw` |
| Building, buildings-only (working tree) | `include_building_features=False`, `buildings_only_mode=True` | roads + `buildings` | `edges_raw`, `gdf_all_raw` |
| Line (`mp_noir_gold`, `vintage_atlas`) | `include_building_features=True` | roads + all 9 layers | `edges_raw`, `gdf_all_raw`, `water_raw`, `green_raw`, `coast_raw` |

- **Tags.** Per layer exactly `_FEATURE_LAYER_SPECS[layer]["tags"]`. The store's `TagRules.from_production()` already covers all nine layers (M2), so no store rebuild was needed.
- **Geometries.**
  - `edges_raw`: LineStrings indexed `(u, v, key)`.
  - Feature layers: OSMnx `(element, id)`-indexed GeoDataFrames in EPSG:4326 with Point, LineString, Polygon and MultiPolygon geometries.
- **Empty layers.** The engines depend on the production empty-layer outcomes:
  - `coast_raw=None`, with the Hungarian message printed;
  - `islands_raw` as an empty EPSG:4326 GeoDataFrame;
  - any other empty layer raises `InsufficientResponseError`.
- **OSMnx steps.**
  - Roads: `graph_from_point(dist=dist_m, custom_filter=_ROAD_CUSTOM_FILTER, simplify=True)`, i.e. `graph_from_polygon` with a 500 m buffer → truncate → largest component → simplify → truncate → largest component → `street_count`. Then `graph_to_gdfs(nodes=False)`.
  - Features: `features_from_point(tags, dist=dist_m)` per layer, i.e. `_create_gdf` (`_process_features` + `_filter_features`).
- **Result.** The Building and Line engines need nothing beyond the bundle dict. **No interface gap; no production change required.**

#### 11.4.2 Implementation (`generator/core/pbf_source.py`)

- **Import-time guard.** `check_osmnx_contract()` requires `osmnx==2.0.7`. It also requires the positional signatures `_create_graph(response_jsons, bidirectional)` and `_create_gdf(response_jsons, polygon, tags)`; otherwise it raises `OsmnxContractError`.
- **`PbfBundleSource(reader).load_bundle(...)`.** Same keyword signature and defaults as the production loader (test-enforced). Returns `_assemble_runtime_bundle(...)` for exactly the layers `_select_required_feature_layers` requests.
  - `use_cache` is ignored: the store is the cache, so no pickles are written.
  - Per-call statistics go to `last_stats`.
- **Query geometry.**
  - `dist_m` uses the production formula.
  - The polygon is `bbox_to_poly(bbox_from_point(center, dist_m))`.
  - The road polygon is that polygon buffered by 500 m in UTM.
  - Both are test-verified to equal the polygons the production loader hands to Overpass.
- **Coverage.** `CoverageError` is raised before any processing if the buffered road box is not inside the PBF header bbox. There is no fallback to Overpass.
- **Selection** (the plan §7.1 assumption, same rule as `FakeOverpass`):
  - Ways: their node line intersects the polygon (vectorized shapely).
  - Nodes: inside the polygon.
  - Relations: an R*Tree candidate with the layer bit and either a member way selected or a member node inside the polygon.
  - Recursion: nodes of ways plus all members of the relation; nested relations are never expanded.
  - All stored ways in the query bbox are fetched **once** and shared by all layers.
- **Incomplete data** (extract-border truncation):
  - Ways with missing node locations are dropped from roads and features and counted.
  - A relation that thereby loses a member way, or that misses a member in the store, gets OSMnx's own null geometry and is removed by OSMnx.
  - Missing label nodes do not affect geometry.
  - Nothing is repaired or invented.
- **Processing.** The OSMnx private functions are called with the same inputs, followed by the exact `graph_from_polygon` steps. The road-network type is `"all"`, as in `graph_from_point`, so edges are bidirectional only if `ox.settings` says so.

#### 11.4.3 Tests (`tests/pbf_source/`, 46 tests, offline, synthetic PBFs in tmp dirs)

**Datasets** (`pbf_source_data.py`)

- M1 road and feature fixtures, plus every tag family the engines read: `building:part`, industrial, parking, cemetery, square, pedestrian area, beach, harbour, marina, breakwater, trees, level crossing, path/steps/track, canal, basin.
- Relation edge cases:
  - selected only through an untagged label node, with an enclosing outer ring;
  - nested relation member;
  - missing label node;
  - missing member way.
- A complete way crossing the extract boundary.
- An optional coastline and islands.
- `truncated_dataset()` adds:
  - a road with a missing node;
  - a road cut at the extract boundary;
  - a building with a missing node;
  - a multipolygon whose member way is truncated.

**Test modules**

- **`test_pbf_source_contract.py`:**
  - OSMnx version and signature guards (positive and negative);
  - `dist_m` equal to production for 3 viewports;
  - query and road polygons exactly equal to production's Overpass polygons;
  - `CoverageError`;
  - loader signature parity;
  - no production import of `pbf_source`/`pbf_store`.
- **`test_pbf_source_parity.py`:**
  - **B4 exact equality.** Adapter bundles equal the production loader + OSMnx + `FakeOverpass` on the same PBF elements for Block, Building/Line and buildings-only modes, with and without coast. This covers every key, row, column value and exact geometry. Only list-valued cells are compared order-insensitively, because OSMnx builds them with `list(set())`.
  - A mutation check showed that a 1e-7° shift in any single layer is detected.
  - Empty-layer outcomes match production.
  - The relation edge cases above.
  - The cross-border way keeps its full geometry.
  - Truncated elements are dropped and counted, with the rest of the bundle **equal** to production on the dataset without them.
  - A missing trees layer raises `InsufficientResponseError` in both paths.
- **`test_pbf_source_engines.py`:**
  - All 11 registered styles render through their real engine function from an adapter bundle (inland and coast stores). Each asserts the loader keywords and the requested layers.
  - Plus Building buildings-only (marked `working_tree`).

- The M1/M2 tests are unchanged.

### 11.4 M3: isolated adapter for all engines (2026-10-26)

#### Engine data contract (verified in code before implementation)

All engines call the module-level name `load_or_build_shared_osm_bundle` imported into their own module, read only the edge table of the road graph, and project each layer separately (§3.5).

| Engine | Loader keywords | Layers loaded (production `_select_required_feature_layers`) | Bundle keys actually read |
|---|---|---|---|
| Block | none (defaults) | `water`, `green`, `coast`, `islands` | `edges_raw`, `water_raw`, `coast_raw`, `islands_raw` (`green_raw` loaded, unused) |
| Building | `include_building_features=not buildings_only`, `buildings_only_mode=buildings_only` | all 9; buildings-only: `buildings` | `edges_raw`, `gdf_all_raw`, `trees_raw`, `waterway_raw`, `railway_raw`, `paths_raw`, `islands_raw`, `coast_raw` (`water_raw`/`green_raw` loaded, unused); buildings-only: `edges_raw`, `gdf_all_raw` |
| Line | `include_building_features=True` | all 9 | `edges_raw`, `gdf_all_raw`, `water_raw`, `green_raw`, `coast_raw` (trees/waterway/railway/paths loaded, unused) |

- **Geometries/tags required:** `edges_raw` LineStrings with `highway` (str or list) and optional `bridge`; feature layers as OSMnx GeoDataFrames indexed by `(element, id)`, EPSG:4326, with the OSM tag columns of §3.5 (`building`, `building:part`, `landuse`, `leisure`, `natural`, `amenity`, `place`, `highway`, `man_made`, `waterway`). Engines tolerate missing columns.
- **Empty-layer semantics (must match production):** `coast` → `None` plus the missing message; `islands` → empty EPSG:4326 GeoDataFrame; any other empty layer → `InsufficientResponseError` propagates (as with Overpass).
- **OSMnx processing:** identical for every engine: the `graph_from_polygon` pipeline for roads and `_create_gdf` per layer. No engine-specific data path exists, so one adapter serves all three.

#### Implementation

- **`generator/core/pbf_source.py`** (new, isolated, not imported by production):
  - Import-time guard: `osmnx==2.0.7` and positional `_create_graph(response_jsons, bidirectional)` / `_create_gdf(response_jsons, polygon, tags)`; otherwise `OsmnxContractError`.
  - `PbfBundleSource(reader).load_bundle(...)`: same keyword signature and defaults as `load_or_build_shared_osm_bundle`; `extent_m`/`use_cache` accepted for parity and ignored (the store is the cache; no pickles are written).
  - Same `dist_m` formula and query polygon (`bbox_from_point` → `bbox_to_poly`); `CoverageError` if the 500 m road-buffered box leaves the PBF header bbox (no fallback).
  - Roads: candidate road ways → segment-intersect with the buffered polygon → `_create_graph` → truncate → largest component → simplify → truncate → largest component → `street_count` → `graph_to_gdfs` edges.
  - Features: all stored ways around the polygon are fetched and intersect-tested **once** per bundle and shared by every layer; per layer: tagged ways/nodes in the polygon, relations (from the relation R*Tree) with a member way in the polygon or a member node inside it, recursion to member ways and nodes, then `_create_gdf` with the production `InsufficientResponseError` handling; bundle assembled by the production `_assemble_runtime_bundle`.
  - Incomplete data: ways with missing node locations are dropped and counted; relations that lose a member way get a null geometry from OSMnx and are removed by OSMnx. Nothing is repaired or guessed.
  - Per-call statistics in `last_stats` (selection counts, dropped/incomplete counts, relations not in the result, timings).
- **Renders:** `C:\DEV\MapCanvas\pbf_poc_render\render_engines_from_pbf_store.py` (one style per process; outside Git) swaps the loader name in all three engine modules in memory, blocks `requests` and both OSMnx Overpass download functions, verifies the store with sha256, and calls the unchanged `render_dispatcher.render_product(preview_mode=False, use_cache=False)`. `run_m3_batch.py` runs all styles sequentially.

#### Synthetic tests (`tests/pbf_source/`, 46 tests, offline)

- `test_pbf_source_contract.py`: version/signature guards; `dist_m` equals production for 3 viewports; the network and feature query polygons equal the production Overpass polygons exactly; `CoverageError` before any processing; loader signature parity; no production module imports `pbf_source`/`pbf_store`.
- `test_pbf_source_parity.py`: **bundle equality** (all 10 keys, geometry and attributes) between the adapter and the real production loader + OSMnx fed by FakeOverpass with the same PBF elements, for Block, Building/Line and buildings-only modes × inland/coast datasets; empty coast/islands handling; relation edge cases (selection via an untagged label node of an enclosing boundary, nested relation member, missing label node, missing member way); complete way crossing the extract boundary keeps its full geometry; truncated road/building/relation member and a border-cut road are dropped with bundles equal to the reference without them; a missing required layer raises like production. A mutation check (1e-7° shift) confirmed the comparison detects changes in every layer.
- `test_pbf_source_engines.py`: all 11 registered styles render through their real engine function from an adapter bundle (inland and coast stores), asserting the loader keywords each engine passes; buildings-only mode (`working_tree`).
- Equality is under the FakeOverpass selection rule, i.e. the §7.1 assumption shared with the adapter; it is not proof of real Overpass selection.

#### Acceptance renders (Budapest 47.4979, 19.0402; `EXTENT_M=3000`; 50x70; 300 dpi spec; source `hungary-260918.osm.pbf`, sha256 `dc2c1dae…cbf2eb2`)

Outputs: `C:\DEV\MapCanvas\pbf_poc_render\m3_engines_budapest_3000m_50x70_20261026_230304\<run>\` (SVG, PNG, PDF, preview WebP, `run_log.json`, console log); aggregated in `m3_validation_summary.json`. The M2 baseline directory is untouched.

| Run | Engine | Wall (process) | Bundle | `render_product` | Peak working set | PDF drawings | PDF bytes |
|---|---|---|---|---|---|---|---|
| urban_modern | Block | 69.7 s | 25.7 s | 61.7 s | 1.13 GB | 26,906 | 1,232,256 |
| midnight_ember | Block | 71.7 s | 27.2 s | 63.8 s | 1.13 GB | 26,906 | 1,232,021 |
| mp_noir_gold | Line | 117.4 s | 37.2 s | 108.3 s | 2.26 GB | 41,858 | 1,003,873 |
| vintage_atlas | Line | 107.9 s | 36.4 s | 98.9 s | 2.26 GB | 42,850 | 1,327,338 |
| midnight_blue | Building | 83.5 s | 35.0 s | 73.7 s | 2.25 GB | 21,178 | 1,933,297 |
| architect_sage | Building | 106.5 s | 38.5 s | 96.5 s | 2.26 GB | 34,431 | 2,284,036 |
| warm_terracotta | Building | 99.8 s | 37.2 s | 88.9 s | 2.26 GB | 34,431 | 2,284,055 |
| mono_black | Building | 92.1 s | 40.6 s | 82.6 s | 2.26 GB | 25,196 | 1,948,764 |
| royal_purple | Building | 170.6 s | 38.4 s | 159.0 s | 2.26 GB | 77,675 | 3,202,773 |
| sandstone_beige | Building | 155.7 s | 36.5 s | 141.9 s | 2.25 GB | 77,675 | 3,204,674 |
| luxury_gold | Building | 85.2 s | 34.7 s | 73.4 s | 2.26 GB | 26,838 | 2,160,178 |
| midnight_blue buildings-only (working tree) | Building | 62.4 s | 31.7 s | 53.5 s | 2.25 GB | 15,245 | 1,450,203 |

- **Common to all runs:** exit 0; no exceptions; 0 Python warnings; OSMnx log 809 lines, all INFO, 0 WARNING/ERROR; PNG 1890 × 2646 px; PDF 1 page, 1417.32 × 1984.25 pt (50.0 × 70.0 cm), **vector-only** (0 raster images), title as outlines.
- **Bundle (identical in every run):** `edges_raw` 95,034 (graph 35,534 nodes; 38,508 road ways); buildings 41,401; trees 14,128; waterway 162; railway 7,289; paths 17,496; water 90; green 2,666; islands 3; coast empty (`None`). 0 incomplete ways, 0 relations with missing members, 0 relations dropped. Area selection: 81,551 candidate ways, 443,653 nodes, 3.9 s.
- **Regression check:** the M3 `urban_modern` PNG is **pixel-identical** to the M2 baseline PNG and the bundle counts match exactly (the M3 relation selection uses the relation R*Tree plus member-node tests instead of member lookups; no difference in Budapest).
- **Bundle time:** 25–41 s, of which the road graph is ~19–23 s (OSMnx graph construction/simplification dominates, not the store).
- **Visual inspection (all 12 previews):** Danube, Margaret Island, bridges, Castle Hill, Parliament, boulevards, railway yards and parks present; dense building footprints in the Building styles; no blank regions, frame clipping, broken polygons or style regressions found. A suspected right-edge notch was checked at full resolution: it is the Grand Boulevard meeting the frame.
- **Driver defects found and fixed (no effect on maps):** the driver set `ox.settings.log_folder` (OSMnx 2.0.7 uses `logs_folder`), so OSMnx wrote one combined log to `city_map_generator/logs/` (cwd) and the per-run OSMnx warning counts in `run_log.json` are empty. That log was created by this batch, was moved to the batch directory as `osmnx_combined_all_runs.log`, and the folder removed; its content is the 809-line INFO-only log above. Preview WebPs target ≤150 KB; four exceeded it (up to 195 KB) at the lowest quality step (preview only).

#### Engine status

| Engine | Status | Evidence |
|---|---|---|
| Block | **PASS** | 2/2 styles; pixel-identical to the M2 baseline; parity tests |
| Building | **PASS** | 7/7 styles + buildings-only mode; parity tests (Building/Line and buildings-only modes) |
| Line | **PASS** | 2/2 styles; parity tests (Building/Line mode) |

#### Limitations and remaining risks

- **Overpass selection rule** (§7.1) remains an assumption; PASS means the engines consume the store-built bundles correctly, not that maps equal Overpass maps. Measuring that is M6.
- **Extract-border data:** relations losing a member way at the border are dropped (OSMnx behaviour); complete ways crossing the border are kept. None occurred in Budapest; border cities need M6 comparison.
- **Memory:** 2.25 GB peak per Building/Line render vs 1.13 GB for Block (bundle + rendering of ~100k features). The Overpass path was not measured on the same machine.
- **Snapshot age:** data is the 2026-09-18 extract; refresh is out of scope (§13).
- **Unchanged open items:** preview-mode PNG/SVG mismatch bug, print-PDF retention task (§9), OSMnx private-API dependency (guarded).

### 11.5 M6: targeted Overpass vs PBF comparison, Budapest (2026-10-26): BLOCKED

**Scope.** One acceptance case only: Budapest 47.4979, 19.0402, `EXTENT_M=3000`, 50x70, `urban_modern` (Block engine). It is a targeted acceptance test, not a parity proof for other locations or extract borders.

**Step 1 findings (inspection)**

- **No usable Overpass reference exists.**
  - Repo `cache/` (121 files) holds bundle pickles and HTTP responses only for Moscow, Prague, Istanbul, Catania and Poole.
  - The workspace-root OSMnx HTTP cache (`C:\DEV\MapCanvas\cache`, 44 responses, Overpass base timestamps 2026-08-07 to 2026-08-12) has no response whose bounds touch Budapest.
  - `GEOFABRIK/` Budapest artefacts are PBF-derived.
- **Minimum request budget for this case: 5 Overpass POSTs**, plus OSMnx's `/status` checks.
  - The requests are 1 road-network query (500 m-buffered box, ~9.1 × 9.1 km, far below the 2,500 km² subdivision threshold, so no split) and 4 feature queries: `water`, `green`, `coast`, `islands`, the layers the Block path requests.
  - Buildings, trees, waterway, railway and paths are not requested by `urban_modern` and were deliberately not queried.
- **Planned method** (scripts outside Git: `C:\DEV\MapCanvas\pbf_poc_render\m6_capture_overpass.py`):
  - Run the unchanged production loader once (`use_cache=False`, so no pickles), with OSMnx's HTTP cache redirected to a new M6 directory.
  - Replay those responses offline, with requests blocked, for every later step.
  - Compare layers by stable `(element, id)` and edge `(u, v, key)` keys and geometry, after capturing the raw elements passed to `_create_graph`/`_create_gdf` on both paths.
  - Attribute differences with at most one extra `out meta` query for the differing IDs, comparing against the PBF snapshot time 2026-09-18T20:21:10Z.

**Live capture attempt** (M6 dir: `C:\DEV\MapCanvas\pbf_poc_render\m6_overpass_vs_pbf_budapest_20261026_234938\`, holding `capture_log.json` and the OSMnx log)

| UTC | Request | Result |
|---|---|---|
| 22:48 (manual check) | GET `/api/status` | HTTP 200 after 38 s through the proxy; first attempt (20 s timeout) timed out |
| 22:49:40 | GET `/api/status` (OSMnx rate-limit check) | `ProxyError`: **407 Proxy Authentication Required** (corporate proxy); OSMnx fell back to a 60 s pause |
| 22:50:40 | POST `/api/interpreter` (road network) | **HTTP 502: "This Overpass API server is currently at capacity. All query workers are busy and the request queue is full."** The server advises exponential backoff and a self-hosted instance for automated use |

The production loader raised `ResponseStatusCodeError` after this one POST, because there is only one endpoint and no retry. No response was cached and no reference bundle exists. Per the M6 stop rule, I did not retry in a loop, switch endpoint or substitute PBF output as the reference.

**Outcome**

- Steps 2 to 4 (layer comparison, dual render, diff image) **were not performed**.
- No Overpass-vs-PBF measurements exist yet.
- The Overpass selection rule (§7.1) remains unresolved.
- **Decision: NO-GO for M4 (acceptance not demonstrated).** This is not evidence of a PBF defect: the comparison is blocked, not failed. The existing evidence (M3 synthetic parity, 12 clean Budapest renders) does not cover real Overpass selection or the snapshot difference.

**Safeguards after the attempt.** Unchanged: Git status, the diff hash (`7D5598…CE7`), `requirements.txt`, repo `cache/` + `output/` (121 files), root `cache/` (44), `GEOFABRIK/` (16), the store, and all 111 protected M1–M3 code, test and output files. No `logs/` folder was created in the repo. Offline suite: **596 passed, 2 skipped** (identical to M3).

**Options to unblock (each needs approval)**

1. **Single retry later** in an off-peak window with the same 5-request budget, after confirming the proxy authenticates (407 seen on the status endpoint). OSMnx itself retries 429/504 but not 502.
2. **Alternative public endpoint** (for example `overpass.kumi.systems` or `overpass.private.coffee`) for this one capture only, set via `OSM_OVERPASS_ENDPOINTS` for the capture process. It changes the reference server, not production code.
3. **Overpass attic query** `[date:"2026-09-18T20:21:10Z"]` for the same 5 queries. It removes snapshot-age differences and isolates selection semantics, but is heavier on the server.
4. **Self-hosted Overpass** loaded from the same Hungary PBF. It removes both rate limits and snapshot differences, but is a larger effort.

### 11.6 M4: opt-in source switch in the production loader (2026-10-27)

**Decisions (user, 2026-10-27).**

- Proceed with M4 although M6 is blocked (§11.5).
- Edit `osm_bundle_cache.py` **additively on top of the uncommitted working-tree changes**. The switch must live there because `render_building.py` and `render_line.py` import the loader name directly.
- **No pickle cache for PBF bundles**: the store is the cache.

**Change**

- **`generator/core/osm_bundle_cache.py`** (+26 lines, 0 changed or removed):
  - `_selected_osm_source()` reads `MAPCANVAS_OSM_SOURCE`: unset, empty or `overpass` (case-insensitive) selects Overpass; `pbf` selects the PBF store; anything else raises `ValueError`.
  - The PBF branch sits at the top of `load_or_build_shared_osm_bundle` and lazily imports `pbf_source.load_bundle_from_env`.
  - The Overpass branch is the unchanged `_build_shared_osm_bundle` call.
  - The working-tree diff of the file changed only by these added lines (verified line by line against the pre-M4 diff); the other four modified files are unchanged.
- **`generator/core/pbf_source.py`:** new `load_bundle_from_env()`.
  - `MAPCANVAS_PBF_STORE_DIR` is required (`PbfStoreError` otherwise); `MAPCANVAS_PBF_PATH` is optional and makes the reader check source size and mtime.
  - It prints one `[OSM] Source: PBF store … (snapshot …)` line.
  - It reads and writes no pickles; `use_cache` is ignored.
- **Coverage and failures:** a query outside the PBF header bbox raises `CoverageError`, with no fallback to Overpass.
- **Unchanged:** `requirements.txt` (osmium stays in `requirements-pbf.txt` and is only imported when `pbf` is selected), Overpass cache filenames and behaviour, engines, layouts, dispatcher.

**Tests** (offline)

- `tests/pbf_source/test_source_switch.py` (13 tests):
  - default, empty, `overpass` and `" OVERPASS "` take the Overpass path, and the PBF function is forbidden;
  - the `pbf` bundle equals the Overpass/FakeOverpass bundle through the production entry point, with no Overpass calls and nothing written to the cache dir even with `use_cache=True`;
  - a missing store dir, a PBF path mismatch, out-of-coverage and an unknown value each raise;
  - Overpass cache filename format is unchanged;
  - Block, Building and Line engines reach the PBF path through their own imported loader name.
- The M3 isolation test now asserts the M4 contract: `osm_bundle_cache.py` is the only production importer of PBF code, and only lazily.
- New repo-level `conftest.py`: an autouse fixture removes `MAPCANVAS_OSM_SOURCE`, so a developer shell with `pbf` set cannot reroute the offline suite. Verified by running the suite with the variable set.
- **Full offline suite: 609 passed, 2 skipped** (596 + 13). The clean-`HEAD` subset gives 603 passed, 2 skipped, 6 deselected. The result is identical with `MAPCANVAS_OSM_SOURCE=pbf` set in the shell.

**End-to-end acceptance**

- Run: production `render_product` with `use_cache=True`, PBF selected only via environment variables, network blocked.
- Script and outputs: `C:\DEV\MapCanvas\pbf_poc_render\m4_switch_acceptance.py` → `C:\DEV\MapCanvas\pbf_poc_render\m4_switch_budapest_20261027_000914\`.

| Style (engine) | `render_product` | Peak working set | PDF | PNG vs M2/M3 output |
|---|---|---|---|---|
| urban_modern (Block) | 63.3 s | 1.13 GB | 1 page, 1417.32 × 1984.25 pt, 26,906 drawings, 0 raster | **pixel-identical** |
| midnight_blue (Building) | 72.1 s | 2.29 GB | same page size, 21,178 drawings, 0 raster | **pixel-identical** |
| mp_noir_gold (Line) | 105.7 s | 2.29 GB | same page size, 41,858 drawings, 0 raster | 0.21 % of pixels differ (isolated road segments; `diff_vs_m3.png`) |

**Why `mp_noir_gold` differs (existing behaviour, not a data difference)**

- The Budapest bundle was built twice through the switch under `PYTHONHASHSEED=1` and `=2`.
- Identical: 95,034 edges, the same `highway` **sets**, and an identical edge-geometry hash.
- Different: the list **order** on 3,565 of 3,852 merged edges.
- Line and Building styles color roads by the first list element (§6.3, §15), so Line output varies between processes on either source. Building is affected the same way in principle; it was identical here.

**Rollback.** Unset `MAPCANVAS_OSM_SOURCE`, or remove the added lines (`_OSM_SOURCE_ENV`, `_OSM_SOURCES`, `_selected_osm_source`, and the `if … == "pbf"` block) from `osm_bundle_cache.py`.

**Limitations and risks after M4**

- **No real Overpass comparison yet** (§11.5). The selection rule (§7.1) and the snapshot difference stay unmeasured, so `pbf` should stay opt-in until M6 runs.
- **Commit hygiene:** M4 lines and the user's uncommitted work share `osm_bundle_cache.py`; stage with `git add -p`.
- **Memory:** about 2.3 GB per Building/Line render with `pbf`.
- **Coverage:** Hungary extract only; anything else raises `CoverageError`.

**Files that stay untouched throughout:**

- `generator/engines/*`, `generator/layouts/*`, `generator/core/render_dispatcher.py`, `generator/core/bundle_viewport_policy.py`, `generator/styles.py`, `generator/specs.py`;
- the POC scripts;
- existing cache files.

---

## 12. Risks and rollback

| Risk | Mitigation |
|---|---|
| Private OSMnx API changes | Exact pin, an import-time version and signature guard in `pbf_source.py` (M3) and contract tests; the XML fallback only with separate approval (§0.1) |
| Overpass selection differs (enclosing features) | **Explicit migration risk.** Overpass-compatible selection mode by default; documented limitation (§7.1). The M1 fake does not settle it. |
| Regional border truncation | Count missing references; raise a coverage error when the query box falls outside the PBF bounds |
| Store size and query performance | Measure in M8; no target numbers assumed |
| The two sources mixing in the cache | Source token in PBF cache keys; separate store directory |
| UTM zone mismatch between layers (existing) | Documented; not changed in this migration |
| Uncommitted work-in-progress in the working tree | Line references refer to the current working tree; recheck before each milestone |

**Global rollback:** leave `MAPCANVAS_OSM_SOURCE` unset (the Overpass default) and revert the milestone's change.

---

## 13. Future S3 and regional-data architecture (design only)

- **Regional manifest:** region ID, bounds polygon, source URL or S3 key, version, sha256.
- **Choosing a region:** the region whose bounds contain the full `dist_m` query box. If none does, raise an explicit error; no silent fallback.
- **Local cache:** `MAPCANVAS_PBF_STORE_DIR/<region>/<version>/` holding the PBF and the preprocessed store. A file lock is used while building, and an atomic directory swap on refresh. Old versions are kept until no job references them.
- **Jobs:** workers read only from local versioned stores. Preprocessing runs as a separate job when a new extract arrives.
- **Credentials:** from the environment or an IAM role only, never in code. Local development works without AWS by pointing `MAPCANVAS_PBF_PATH` at a local file.

---

## 14. Unresolved questions and blockers

1. The Overpass `(poly:…)` selection rule for ways and relations (§7.1). The M6 live probe was blocked by Overpass capacity (HTTP 502) and a proxy 407 (§11.5).
2. ~~Whether the Geofabrik extract keeps ways and relations complete at the border.~~ **Measured (S4):** 0 missing node references. 8 relations miss 115 members in total. The border test boxes were complete (§11.2).
3. ~~Final choice between the private OSMnx functions and the public XML fallback.~~ **Resolved:** private functions, version-guarded; equivalence verified offline in M1.
4. ~~Whether pyosmium 4.3.1 supports the planned multi-pass extraction.~~ **Resolved (M2):** yes. `add_references` runs during the live iteration, followed by `complete_backward_references(relation_depth=0)`.
5. ~~Whether SQLite R*Tree is available in the Python 3.14 Windows build.~~ **Resolved:** SQLite 3.50.4 with R*Tree and JSON1.
6. ~~Whether to keep the existing randomised `highway` list order.~~ **Resolved:** preserved; deterministic styling is in §15.
7. No webshop print entry point exists yet (§9). This is a separate required production task.
8. `osmium==4.3.1` is declared in `requirements-pbf.txt` (M2). `requirements.txt` is unchanged. Since M4 osmium is imported only when `MAPCANVAS_OSM_SOURCE=pbf`. `pytest` is declared in `requirements-dev.txt` (M1).
9. The five uncommitted user changes (§2.1) are preserved as they are. While they remain uncommitted, the working-tree baseline differs from `HEAD`.

---

## 15. Future improvements (outside this migration)

1. **Deterministic road styling.** Merged edges' `highway` lists come from `list(set(...))`, and Building and Line style by the first element, so styling can differ between runs. A deterministic rule, for example choosing the highest-ranked road class, would change the visual output and needs its own approval.
2. **Edge truncation at the query box** (§6.2). An optional strategy that cuts simplified edges at the box instead of dropping them could be evaluated. It would change the road data the engines receive.
3. **Single explicit rendering CRS** (§8), replacing the per-layer automatic UTM selection.
