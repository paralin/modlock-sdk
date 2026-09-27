# Runtime findings

Measured on September 20, 2026. These results distinguish verified source
identity, successful compilation, editor startup, and complete authoring flows.
No community executable was used.

## Verified assemblies

| Profile | Selected files | Bytes |
| --- | ---: | ---: |
| CS2 compiler/tools | 2,673 | 2,512,744,857 |
| Dota compiler/tools | 2,796 | 1,815,437,333 |
| Deadlock runtime/content | 3,862 | 36,514,514,979 |

The profiles and recipes pin every depot/manifest and file hash. CS2 requires
`game/csgo_core/` from Workshop Tools, including `models_gamedata.fgd` and
`readonly_tools_asset_info.bin`. Dota requires its DirectX shader depot 373302;
omitting it produced missing `error.vfx` diagnostics. Its profile excludes the
Workshop copy of `dota.signatures` and retains the common-depot version.

On Windows, 2,200 CS2 and 3,654 Deadlock installed files matched the pinned
recipes and were copied into an isolated workspace. The remaining 473 CS2 files
came from the verified local assembly; 208 Deadlock files were downloaded from
the pinned Valve depots and checked before and after transfer. Existing Steam
installations were not modified. Windows did not have rsync; transfers used an
SSH tar stream. All reuse was conditional on matching hashes, not installation
names or apparent version numbers.

## Environments

- Linux x86-64, Valve Proton `1788504981 proton-11.0-2c-x86_64`, Xvfb and
  WineD3D. A bare Wine prefix failed to load `rendersystemdx11.dll`; Proton
  initialization supplied the runtime environment. Direct Proton stdout did
  not capture the compiler's child output, so the probe uses cmd redirection.
- Windows 10 Pro, build 19045, Radeon RX 6700 XT, driver 32.0.21045.5002.
  The OpenSSH service session exposed no usable display outputs. Compiler
  probes used software rendering successfully. The editor required the active
  console desktop session, reached through a temporary scheduled task with an
  Interactive principal. No password or saved credential was read.
- Windows scripts used the official Python 3.14.0 x64 embeddable package from
  [Python.org](https://www.python.org/downloads/release/python-3140/), ZIP SHA-256
  `8d4d3590c10449d78aa4375f534e6d5f3027d67fdc362dd1a882279db6f90fdf`.
  Regular Python 3.11+ also satisfies the scripts. The embedded distribution's
  isolated import path needs the workspace scripts directory when invoking
  `tool_project.py`; a normal Python installation does not need that adjustment.

## Measured compatibility

| Combination | Linux/Proton | Native Windows |
| --- | --- | --- |
| CS2 compiler, CS2 context, Panorama | Pass, two identical forced runs | Pass, two identical forced runs |
| Dota compiler, Dota context, Panorama | Pass, two identical forced runs | Not tested |
| CS2 compiler, authored Citadel content project, Panorama | Pass | Pass, with authored configuration |
| CS2 compiler, CS2 context, ModelDoc cube | Not tested | Pass, two identical forced runs |
| CS2 compiler, authored Citadel content project, ModelDoc cube | Not tested | Pass, with authored configuration |
| CS2 compiler, untouched Deadlock context | Rejects obsolete `Valve_TestPlurals:p` localization token | Not retested |
| Dota compiler, untouched Deadlock context | Same localization rejection | Not tested |
| Deadlock compiler DLL plus CS2 compiler launcher | Missing `modeldoc_utils`, error 126 | Same missing module, error 126 |
| Deadlock compiler plus 131 absent CS2 bin/core files, including launcher | Access violation `0xc0000005`, address `0x41` | Cannot load `modeldoc_utils`, error 127 (missing procedure) |

The Windows result establishes that the supplemented configuration also fails
natively; its failure differs from the Proton crash. Do not treat those DLL
sets as interchangeable. The Windows experiment removed its 131 supplemental
files and test addons afterwards.

Compiler receipts record executable/DLL/configuration hashes, output hashes,
exit codes and log names. The final probe also records source fixture hashes.
Identical output is checked within one addon/workspace. Different addon names
and source line endings can change embedded resource metadata.

The authored cube decodes through the pinned Source2Viewer CLI as eight vertices,
36 indices and bounds `[-16,-16,-16]` to `[16,16,16]`; see
`windows-model-inspection.json`. Its material must explicitly name
`materials/dev/color_purple.vmat`. An unnamed OBJ material became `default.vmat`
and failed CS2's missing-material policy. That was a fixture defect, not a
reason to disable the compiler's material checks.

## Reconstructed configuration and editor startup

`tool_project.py` mounts 461 verified Deadlock asset packages while preserving
the coherent CS2 engine, core, localization and shaders. It creates writable
Citadel source/configuration directories, supplies generic Valve ModelDoc
metadata and the generated entity FGD, and disables foreign game app systems.
The configuration is for content authoring; it does not run Deadlock gameplay
inside the CS2 engine.

The stock CS2 launcher selected `csgo` despite a `-game` argument. The small
source-built launcher calls the adjacent engine's exported `Source2Main` with
`citadel` as the game argument. Zig 0.16.0 built the inspected executable;
its hash and the engine hash are in startup reports.

The first desktop launch initialized graphics and scanned the correct mounts,
then failed to read `user_keys_default`. The verified file already existed at
`game/core/cfg/user_keys_default.vcfg`. Adding `Mod core` to SearchPaths fixed
the lookup; `Game core` alone was insufficient. A subsequent `+quit` launch
reached `Source2Init OK`, returned zero, and shut down Qt and Source 2 normally.

ModelDoc initially showed `Failed To Load Entity FGD`. Reducing the input to
Valve includes alone passed; bisection isolated a redeclaration of
`env_combined_light_probe_volume`. The merger's original expression stopped at
`box_min = "box_mins"` inside an editor attribute, so it missed the actual class
name and generated a duplicate. The header scanner now skips quoted strings,
comments and nested attributes before reading the top-level class assignment.
This removes 19 duplicate Valve classes and retains 89 additional observed ones.
The regression fixture includes nested assignments and quoted delimiters.

The final configuration selects that FGD once through `Hammer/fgd`. The loader
also reads `fgd_files`; an empty filename in an earlier error message did not
establish that this newer setting was unsupported. `LayeredOnMod core` retains
Valve's generic render modes and pipeline aliases. Without the inherited render
defaults, the cube preview reported material layers with no valid vertex-shader
signature. These corrections preserve the baseline core file.

The desktop editor probe starts each tool, observes it for 35 seconds, records
only its own window titles and SDK modules, then closes its own process tree.
The observations opened Hammer, ModelDoc with `models/probe.vmdl`, and Source
Filmmaker. It takes no screenshots and does not claim a visual quality check.
All three final runs closed with exit zero and no error dialogs. Their complete
logs and configuration hashes are in `final-editors/`; the final compiler
receipts are `windows-release-model.json` and `windows-release-panorama.json`.
Hammer needed the bounded forced-close fallback in an initial run; that older
observation is retained separately.

## Remaining authoring checks

- Create, save and compile a Hammer map, then load that map in current Deadlock.
  Startup logs still report missing game-specific detail-prop/water definitions
  and a default editor preview scene. Their impact on a particular map or
  preview requires its own check.
- Exercise a Citadel model's animation events and game data. Generic model
  compilation works; game-specific metadata is not reconstructed completely.
- Create and render an SFM scene with a representative Deadlock model/map.
  Opening the editor does not establish successful scene rendering.
- Load the compiled Panorama/model outputs in the current Deadlock game.
  Compiler success and Source2Viewer decoding do not establish game acceptance.

## Entity metadata provenance

The exporter read 185 verified map VPKs and 201 `vents_c` entity lumps. The merger
keeps Valve's core definitions and adds 89 observed classes. The FGD SHA-256 is
`1faaae7460b983594b1ec06fcaff1adb2bee0001036d4f2eb42459332f2fbca3`.
`metadata/entity-sources.json` identifies each map hash, member and entity count.

Neither the checked current manifests nor the core/Citadel VPK indexes contains
the Citadel tools FGD or ModelDoc game-data FGD. Observations cannot recover
unseen fields/classes, editor defaults, enum choices, input signatures, or the
lost distinction between some vector and color values. These limits remain
explicit in the generated definitions.

A fresh native Windows export reproduced all 201 earlier map/member receipts.
Merging those observations on Windows and macOS produced byte-identical final
FGDs. Preserve LF output when writing the generated definitions.

## Continuing workspaces

The isolated Windows workspace retains the final CS2 content project, separate
Deadlock runtime, compiler fixtures, and source-built exporter. The temporary
desktop scheduled task was removed and no test editor remained running.
The Linux host became unreachable before cleanup of its earlier experimental
workspace. Its isolated Deadlock copy still needs the supplemental paths listed
in `tool-supplement.json` removed before further runtime acceptance; its Steam
installation was not modified. Use a fresh recipe assembly for any new check.
