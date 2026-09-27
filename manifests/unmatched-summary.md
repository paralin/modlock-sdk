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

## Current reconstruction and remaining acceptance

1. **Deadlock runtime and content: assembled and verified.** The pinned
   profile now supplies 3,862 files, including current game DLLs, shaders and
   VPKs. Keep its engine separate from the tools engine.
2. **Hammer definitions: inferred from current maps.** The source-built
   exporter reads 185 Valve map VPKs and 201 entity lumps. The merger adds 89
   observed classes beyond Valve's core FGDs. Defaults, choices, unobserved
   classes and input signatures remain unknown; map editing and compilation
   must establish usefulness for the intended workflow.
3. **ModelDoc metadata: generic baseline only.** Valve's model and breakable
   definitions are included. Citadel animation events and game-specific model
   properties still need a source-backed schema and a real authoring check.
4. **Game mounts and tool configuration: authored and compiler-tested.**
   `tool_project.py` copies 461 verified Citadel VPKs into a separate content
   mount while retaining coherent CS2 core and binaries. A source-built
   launcher selects the Citadel content project through `Source2Main`.
5. **Runtime acceptance: partly established.** The CS2 and Dota baseline
   compilers, plus the Citadel content project, compile Panorama twice through
   Proton. See [runtime findings](runtime/README.md) for native Windows results.
   Native Windows compiles the model fixture twice and opens it in ModelDoc.
   Loading assets in Deadlock, editing/compiling a Hammer map, authoring an
   animated model, and rendering an S2FM scene remain separate checks.

The historical archive's four binary profiles have not been reproduced as
interchangeable current configurations. Mixing current CS2 compiler resources
with the untouched Deadlock game context fails localization validation; adding
missing CS2 tool DLLs beside Deadlock's own compiler crashed under Proton.
Neither failure justifies replacing or patching Valve DLLs until the supported
content-authoring path has been tested.

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
