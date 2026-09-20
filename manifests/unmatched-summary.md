# What remains and whether it is needed

The historical comparison leaves 2,800 of 10,864 archive paths unmatched,
representing 2,729,096,739 bytes and 2,241 distinct SHA-256 values. This measures
exact reproduction of the old archive. SDK readiness depends on the required
tools, game integration, and working asset pipelines.

The complete path list is [unmatched-files.tsv](unmatched-files.tsv). Its
archive hashes come from `reference/csdk12.json`; reproduced paths come from
`recipes/valve-verified-subset.json`. Current path candidates come from the
pinned manifests, assembled CS2 recipe, and Deadlock core/Citadel VPK indexes.
No community executable was run for this assessment.

## Where the unmatched paths are

| Archive location | Paths | What matters for the current SDK |
| --- | ---: | --- |
| `game/citadel/` | 1,999 | Game assets, UI, scripts, runtime DLLs, shaders, and game/editor configuration. Use current Valve content where needed; rebuild game-specific editor configuration. |
| `game/bin/`, `bin_cs2/`, `bin_server/`, `bin_tools/` | 409 | Historical runtime/tool binaries and helper files. These contain 166 distinct hashes. Current versions supply many components, but the four profiles' behavior still needs testing. |
| `game/core/` | 203 | Shared editor/runtime data, entity definitions, shaders, UI and audio resources. Use matching current core content; validate the editor features that consume it. |
| `content/` | 131 | Editable maps, lighting scenes, materials, model metadata, and sample sources. Needed for the particular assets/features that use them; generally outside a minimal compiler probe. |
| `game/citadel_addons/` | 45 | Test, hero portrait, UI-pose, and audio example addons. Optional for the base toolchain. |
| Root helpers and `game/_toolsettings/` | 13 | Configuration/map-compiler GUIs, README, a diagnostic list, and saved editor settings. Replace helpers with scripts and initialize fresh settings. |

Within `game/citadel/`, 619 paths are models, 513 materials, 315 Panorama UI,
145 sound events, 129 resources, and 121 scripts. Asset and UI dependencies
must be evaluated for the desired map, model, scene, or gameplay feature.

## Current counterparts

| Observed path status | Unmatched archive paths |
| --- | ---: |
| Corresponding current CS2 file already assembled | 355 |
| Corresponding loose file listed in current Valve manifests | 243 |
| Corresponding member listed in current Deadlock VPK indexes | 1,328 |
| No corresponding path found in the checked current sources | 874 |

The first three groups total 1,926 paths (68.8% of the unmatched set). Binary
aliases are normalized to `game/bin/` for this comparison. A matching name
establishes availability of a candidate, not identical bytes, compatible DLL
interfaces, or equivalent behavior. A VPK index entry does not establish that
the current member payload has been downloaded. The last group may include
renamed files, other Valve sources, obsolete files, and community additions;
it is not a finding that all 874 files are custom or unnecessary.

## Integration work that remains necessary

1. **Deadlock runtime and content.** Current `deadlock.exe`, Citadel
   `client.dll`/`server.dll`, game configuration, and shaders are listed in
   Valve's manifests. Obtain or mount the appropriate current game files for
   Deadlock previews and playtests. The assembled CS2 baseline alone does not
   supply a working Deadlock runtime.
2. **Hammer entity definitions.** The archive's `game/citadel/citadel.fgd`
   includes Valve base/light definitions and adds Citadel-specific entities.
   No file at that path appears in the checked current manifests or indexes.
   Its README credits community authors using CS2 definitions and extracted
   game entities. Rebuild and validate this definition layer for Deadlock map
   authoring; the exact historical file is not the requirement.
3. **ModelDoc metadata.** `game/citadel/models_gamedata.fgd` defines Citadel
   animation events and model metadata, including tagged sounds and camera
   settings. No corresponding path was found in the checked current sources.
   Reconstruct the definitions needed by the model-authoring workflow.
4. **Game mounts and tool configuration.** Author the addon search paths,
   tool/game selection, and launch commands against the selected builds. The
   archive's `gameinfo.gi` mounts its Lua-unlocker addon and enables custom
   tool settings; copying that configuration is not a verified integration.
5. **Runtime acceptance.** Run the current compiler on Windows, load its
   outputs in Deadlock, and exercise Hammer/ModelDoc/S2FM separately. The
   archive README claims different binary profiles trade off Animgraph1
   compilation, projected-particle previews, server previews, and standalone
   map compilation. Those claims have not been validated in the new toolchain.

## Optional or feature-specific additions

The configuration GUIs (`csdkcfg.exe`, `CSDKCfgVPK.exe`, `Project8CfgTool2.*`),
`Deadlock_with_tools.exe`, and `GUIMapCompiler/CS2MapCompiler.exe` can be replaced
with explicit build and launch scripts. Their implementation and provenance
remain unresolved; these executable wrappers are not prerequisites for invoking
Valve's tools directly.

`game/citadel/addons/luaunlocker/` contains a native `server.dll`, linker/debug
artifacts, a configuration file, and a sample Lua script. This is a separate
scripting-enablement feature. It is not needed for the basic compile-only
probe. Establish its required behavior and use reviewed source or a local
replacement if the SDK needs that feature. Debug symbols and import libraries
are not normal runtime requirements.

Sample addons, personalized editor settings, logs, branding images, and extra
lighting scenes do not need historical byte reproduction. Some lighting scenes
and metadata support editor previews, so replace or restore them when testing
those features rather than classifying all source content as disposable.
