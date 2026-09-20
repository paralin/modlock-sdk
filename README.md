# Modlock SDK reconstruction

Reconstruct a toolkit using Valve downloads and explicit, hash-checked file
recipes. Requires Python 3.11+, .NET, and a source build of DepotDownloader.
The Python scripts use only the standard library.

## Current result

The primary target is a **current, pinned Valve toolchain**, assembled without
community executables. The verified baselines are:

| Profile | Files | Bytes | Purpose |
| --- | ---: | ---: | --- |
| `current-cs2-tools` | 2,673 | 2,512,744,857 | Coherent CS2 compiler, editors, core and shaders |
| `current-dota-tools` | 2,796 | 1,815,437,333 | Coherent Dota compiler, editors, core and shaders |
| `current-deadlock` | 3,862 | 36,514,514,979 | Separate current game runtime and content |

The CS2 and Dota compiler baselines pass repeated Panorama XML/JavaScript
compilation through Valve Proton 11.0. A separate Citadel content project also
passes using the coherent CS2 toolchain and 461 verified Deadlock VPKs.
The compiled XML and JavaScript decode correctly with Source2Viewer. Native
Windows also passes the CS2 Panorama probe and an authored ModelDoc cube probe;
the decoded cube contains eight vertices and twelve triangles.

A source-built metadata exporter recovered 89 additional entity classes from
201 entity lumps in 185 Valve map packages. These are observed definitions,
not a complete authoring schema. ModelDoc currently has generic Valve model
metadata; Citadel-specific events and properties remain unresolved.

See [runtime findings](manifests/runtime/README.md) for measured compatibility,
Windows results, limitations, and the remaining editor/game acceptance steps.
Native desktop probes open Hammer, ModelDoc with the compiled cube, and SFM.
Source identity, compilation, editor startup, and complete authoring flows remain
separate claims.

Historical byte matching remains useful provenance research. The combined
verified subset reproduces **8,064 of 10,864 reference paths** (74.2%),
occupying 3,200,566,549 bytes, from Valve downloads.

| Input | App | Depot | Manifest | Matching output paths |
| --- | --- | --- | --- | ---: |
| Windows libraries: 43 files | 730 | 2347771 | 5806169188224907599 | 166 |
| Loose content: 2,120 files | 730 | 2347770 | 2053759441494650084 | 2,150 |
| Core VPK: 7 package files, 1,549 members | 730 | 2347770 | 2053759441494650084 | 232 |
| Workshop Tools: 125 files | 730 | 2347779 | 2145418671218218617 | 239 |
| Common files: 26 files | 1422450 | 1422451 | 886051970741897775 | 26 |
| Windows libraries: 42 files | 1422450 | 1422452 | 1334199870863440742 | 167 |
| Loose content: 2,717 files | 1422450 | 1422456 | 9192361732058507254 | 2,722 |
| Citadel VPK: 172 packages, 3,123 candidate members | 1422450 | 1422456 | 9192361732058507254 | 3,573 |
| Core VPK: 7 packages, 1,324 candidate members | 1422450 | 1422456 | 9192361732058507254 | 1,323 |

These are byte-identical available sources, not proof of which depot the
community assembler originally used. Empty files and common libraries can
have many indistinguishable sources. Alternate matches remain in the plans.

The counts overlap. This historical subset is **not a runnable SDK**. Exact
historical compiler/editor/runtime binaries, modified configuration, and
community additions remain unresolved. The current toolchain above provides
an independent path forward without locating every historical manifest.
No community executable has been run or used as an assembly input.

The combined recipe is `recipes/valve-verified-subset.json` and the local
assembly is `output/valve-verified-subset-expanded/`. Individual plans and
recipes retain each source. `manifests/coverage.json` counts the remaining 2,800 paths by
directory and extension. `reference/csdk12.json`
contains hashes and paths, not the community binaries. The original archive's
SHA-256 is `b5e2bfa958fcceb7bc2e6f0e9723edc914dcb9dcbfdd9717bca42dde482e93af`.

See [the remaining-file assessment](manifests/unmatched-summary.md) for the
complete unmatched-path list, current-source candidates, and which capabilities
still need integration or replacement.

## Build the downloader

Build the existing DepotDownloader checkout, or obtain its source from
`https://github.com/SteamRE/DepotDownloader`. The measured revision is
`e7474cb9ee8a87c0d917489b84c75667a1364aa1` (version 3.4.0, SteamKit2 3.4.0).
Inspect its build inputs before building another revision.

```sh
dotnet build ../depot-downloader/DepotDownloader/DepotDownloader.csproj -c Release
```

Run that command from this workspace. The downloader targets .NET 9 and allows
runtime roll-forward; .NET SDK 10.0.401 and runtime 10.0.12 built and ran it here.
Building from inside its checkout instead selects its `global.json`, which
requires an installed .NET 9 SDK. The DLL and all adjacent build outputs form
the runnable tool; do not copy only the DLL.

## Reproduce the current toolchain

Acquire the three manifests named in `profiles/current-cs2-tools.json` with
DepotDownloader. Use an entitled account for Workshop Tools. Add
`-remember-password` during interactive login to opt into a persistent session;
later requests using the same downloader build path can reuse it. No password
belongs in a command line. A successful `-manifest-only` request normally
reports zero payload bytes downloaded.

```sh
python3 scripts/current_toolchain.py select profiles/current-cs2-tools.json \
  --manifests manifests --output manifests/current-cs2-tools
```

For each profile depot, run the following shape with its pinned IDs:

```sh
dotnet /path/to/DepotDownloader.dll -username <account-name> -remember-password \
  -app 730 -depot <depot> -manifest <manifest> -os windows -osarch 64 \
  -filelist manifests/current-cs2-tools/<depot>.files.txt -validate \
  -dir inputs/current-cs2-tools/<depot>
```

Then verify the downloads and assemble into a new directory:

```sh
python3 scripts/current_toolchain.py recipe profiles/current-cs2-tools.json \
  --manifests manifests --inputs inputs/current-cs2-tools \
  --output recipes/current-cs2-tools.json
python3 scripts/assemble_sdk.py recipes/current-cs2-tools.json output/current-cs2-tools
```

The profile has literal inclusion prefixes, preserves native paths, and rejects
different bytes at an overlapping output path. Verification checks every
manifest size and SHA-1, then records SHA-256 for assembly. Valve sometimes uses
an all-zero hash for an empty, chunkless file; the parser normalizes only that
case to the known empty-file SHA-1. Downloads still must have zero bytes.

To update, resolve all selected depots from the current public build, revise
the pinned profile, and repeat verification in new input/output directories.
Run the repeatable probe against the baseline before adding a content project:

```sh
python3 scripts/compiler_probe.py --sdk output/current-cs2-tools --mod csgo \
  --report acceptance/cs2.json
```

Use `--kind model --addon model_probe --report acceptance/model.json` to test
a source-authored cube and Valve's core material instead. The script contains
both complete fixtures and records input hashes. Use a fresh addon for each run.

That command runs natively on Windows. On Linux x86-64, supply `--proton` and
`--steam` with a graphical `DISPLAY`, including an Xvfb display for a headless
machine. The script creates a private prefix, initializes Proton with WineD3D,
and removes the prefix after stopping its own Wine server. It retains the
report, compiler logs and addon outputs.

Use `profiles/current-dota-tools.json` with app 570 and its four pinned depots
to repeat the same select/download/recipe/assemble sequence. Test with
`--mod dota`. The DirectX shader depot is required. The profile explicitly
resolves the overlapping `dota.signatures` versions; see the runtime findings.
Do not treat old and current DLLs as interchangeable.

## Reproduce the library subset without the archive

Run from this workspace; `uv run python` can replace `python3`.

```sh
python3 scripts/depot_download.py \
  --downloader ../depot-downloader/DepotDownloader/bin/Release/net9.0/DepotDownloader.dll \
  --app 730 --depot 2347771 --manifest 5806169188224907599 --output manifests

python3 scripts/depot_match.py select reference/csdk12.json \
  manifests/manifest_2347771_5806169188224907599.txt \
  --app 730 --output manifests/cs2-windows-current.json

python3 scripts/depot_download.py \
  --downloader ../depot-downloader/DepotDownloader/bin/Release/net9.0/DepotDownloader.dll \
  --app 730 --depot 2347771 --manifest 5806169188224907599 \
  --filelist manifests/cs2-windows-current.files.txt --output inputs/cs2-windows-current

python3 scripts/depot_match.py recipe manifests/cs2-windows-current.json \
  inputs/cs2-windows-current --output recipes/cs2-windows-verified-subset.json

python3 scripts/assemble_sdk.py recipes/cs2-windows-verified-subset.json \
  output/cs2-windows-verified-subset
```

Choose a new assembly destination on reruns. The manifest matcher rejects
truncated dumps, validates paths, and uses size plus SHA-1 to shortlist files.
Recipe creation requires every selected payload to match both the manifest
SHA-1 and the reference SHA-256. Assembly checks SHA-256 again.

The download wrapper uses an anonymous Steam session. It copies the complete
unsigned source build to a fresh temporary entry-assembly path before each
invocation, giving .NET isolated storage a new URL identity. A new working
directory or macOS `XDG_DATA_HOME` does **not** isolate DepotDownloader's saved
account data. The wrapper never accepts passwords or saved-login options. The
temporary runtime is removed afterwards; .NET may retain a small anonymous
account/cache record in the user's Application Support isolated storage.

A denied depot can make DepotDownloader exit zero after downloading nothing.
For manifest requests the wrapper requires a newly generated, complete dump
with the requested IDs. For payloads, the recipe verification step establishes
success. Receipts identify the tool DLL, manifest dump or selection, IDs, and
acquisition time. Keep credentials, depot keys, downloaded binaries, and output
trees out of Git.

## Add loose content and VPK members

Repeat the manifest/select/download/recipe sequence for depot `2347770`, pinned
to manifest `2053759441494650084`. Use `manifests/cs2-content-current.json`,
`inputs/cs2-content-current`, and `recipes/cs2-content-verified-subset.json` as
the corresponding paths. This selects 2,120 files (85,528,462 bytes) and
reproduces 2,150 reference paths.

Build the Source2Viewer CLI from source with .NET 10:

```sh
dotnet build ../ValveResourceFormat/CLI/CLI.csproj -c Release
```

The verified source revision is `1b190f66ea239dbea6e74d166dde802658801593`.
It uses ValvePak 6.0.0.182. The core package set occupies 656,693,693 bytes;
reserve another GiB for extraction. Download and extract unchanged members:

```sh
python3 scripts/depot_download.py \
  --downloader ../depot-downloader/DepotDownloader/bin/Release/net9.0/DepotDownloader.dll \
  --app 730 --depot 2347770 --manifest 2053759441494650084 \
  --filelist manifests/cs2-core-vpk.files.txt --output inputs/cs2-core-vpk

python3 scripts/vpk_match.py reference/csdk12.json \
  manifests/manifest_2347770_2053759441494650084.txt --app 730 \
  --depot-root inputs/cs2-core-vpk --archive game/core/pak01_dir.vpk \
  --extractor ../ValveResourceFormat/CLI/bin/Release/Source2Viewer-CLI.dll \
  --extracted extracted/cs2-core-current --output recipes/cs2-core-verified-subset.json

python3 scripts/depot_match.py merge recipes/cs2-windows-verified-subset.json \
  recipes/cs2-content-verified-subset.json recipes/cs2-core-verified-subset.json \
  --output recipes/valve-verified-subset.json

python3 scripts/assemble_sdk.py recipes/valve-verified-subset.json \
  output/valve-verified-subset
```

Use a new extraction directory on reruns. `vpk_match.py` verifies all package
sizes and SHA-1 hashes against the Steam manifest before invoking the extractor.
It matches members by size/SHA-256 and records package SHA-256 hashes, the VPK
directory path, member paths, and the extractor DLL hash. It does not decompile
assets; decompilation would produce different bytes.

## Continue provenance discovery

CS2 Workshop Tools (`730` / `2347779`) and Deadlock (`1422450`)
denied anonymous access and succeeded through an entitled account. For a fresh
interactive session in Terminal:

```sh
dotnet /path/to/DepotDownloader.dll -username <account-name> \
  -app 730 -depot 2347779 -os windows -osarch 64 -manifest-only \
  -dir /absolute/workspace/inputs/cs2-tools-current

dotnet /path/to/DepotDownloader.dll -username <account-name> \
  -app 1422450 -os windows -osarch 64 -manifest-only \
  -dir /absolute/workspace/inputs/deadlock-current
```

Enter the password and Steam Guard response at the prompts. These direct
commands use the downloader's normal account store. Do not put a password in a
command, recipe, or commit. Run `depot_match.py select` on each resulting dump,
then repeat the pinned payload download and recipe checks above. Authenticated
payload downloads use the same direct command with `-manifest <id>`,
`-filelist <selection>`, and `-validate` in place of `-manifest-only`.

Historical search clues in the reference PE headers are September 8–10, 2025
for the CS2 compiler/Hammer/runtime, December 15–17, 2025 for some engine
libraries, and January 21, 2026 for Citadel client/server. These editable
timestamps only narrow the search; an actual Valve manifest and payload match
must establish each result. Current manifests cannot identify every historical
binary. Files extracted from VPKs need the package hash and member path recorded
separately. Community launchers and the Lua-unlocker DLL require buildable
source or an authored replacement; they are not Valve payloads by assumption.

Historical manifest discovery is optional provenance work. It no longer blocks
building the current pinned toolchain.

## Select large VPK downloads

Download the pinned manifest and its `_dir.vpk` first. The selector verifies
the directory against Valve's manifest before reading member metadata:

```sh
python3 scripts/vpk_match.py reference/csdk12.json \
  manifests/manifest_1422456_9192361732058507254.txt --app 1422450 \
  --depot-root inputs/deadlock-vpk --archive game/citadel/pak01_dir.vpk \
  --extractor ../ValveResourceFormat/CLI/bin/Release/Source2Viewer-CLI.dll \
  --select-packages manifests/deadlock-citadel-vpk.files.txt
```

Acquire that file list using the pinned authenticated downloader command, then
replace `--select-packages` with `--matching-paths`, `--extracted` naming a new
directory, and `--output` naming the recipe. Repeat for `game/core/pak01_dir.vpk`.
Selection matches mounted paths and sizes; extraction verifies package hashes,
then member SHA-256. It can miss renamed members. Full extraction without
`--matching-paths` remains available for exhaustive content matching.

The Citadel package staging occupied 18,417,573,193 bytes. Its numbered packages
were removed after verified extraction to recover disk space; the extracted
members, directory, pinned download list, and per-package hashes remain. Re-run
the same download before repeating extraction. Assembling its recipe needs
only the retained member tree.

Compiler and editor checks are separate. The automated probe requires both
`.vxml_c` and `.vjs_c` outputs with stable hashes across two forced compilations.
Hammer map authoring, ModelDoc model authoring, S2FM rendering, and loading the
compiled assets in the current Deadlock game still need their own acceptance.

## Reconstruct the Deadlock content project

Acquire the three pinned depots in `profiles/current-deadlock.json`, then run
the same `current_toolchain.py select`, `recipe`, and `assemble_sdk.py` sequence
using `current-deadlock` input/output names. A Steam installation may supply
inputs when every selected file passes the manifest verification; copy the
verified assembly into a new workspace before experimenting.

The tools-specific FGD is absent from the checked current Valve manifests and
core/Citadel VPK indexes. Recover observed entity definitions from the verified
map packages using the source-built ValveResourceFormat library:

```sh
dotnet build tools/EntityMetadata/EntityMetadata.csproj -c Release \
  -p:ValveResourceFormatProject=/absolute/ValveResourceFormat/ValveResourceFormat/ValveResourceFormat.csproj
```

Run the exporter over every map, including scene and portrait packages:

```python
from pathlib import Path
import subprocess

maps = sorted(Path("output/current-deadlock/game/citadel/maps").rglob("*.vpk"))
subprocess.run([
    "dotnet", "tools/EntityMetadata/bin/Release/net10.0/EntityMetadata.dll",
    "extracted/map-entities", *map(str, maps),
], check=True, timeout=120)
```

Merge the observations with Valve's core FGDs and mount the content in a fresh
CS2 tools assembly:

```sh
python3 scripts/entity_fgd.py extracted/map-entities \
  --core output/current-cs2-tools/game/core --output authored/citadel.fgd
python3 scripts/tool_project.py --tools output/current-cs2-tools \
  --runtime output/current-deadlock --recipe recipes/current-deadlock.json \
  --fgd authored/citadel.fgd
python3 scripts/compiler_probe.py --sdk output/current-cs2-tools --mod citadel \
  --report acceptance/citadel.json
```

The content project preserves the CS2 engine and core resources. It includes
both `Game core` and `Mod core`; the latter is required for default keybindings.
`LayeredOnMod core` retains Valve's render defaults. `Hammer/fgd` identifies the generated definitions once. The merger handles
nested assignments in Valve's class headers, so it preserves those classes
instead of redeclaring them.
It creates writable Citadel source and configuration directories. It mounts only
verified Deadlock VPKs, without loading foreign game DLLs. Its `assembly.json`
records the runtime recipe and generated FGD hashes. It is not an integrated
Deadlock gameplay preview.

Build the Citadel project launcher from source using Zig 0.16.0:

```sh
zig cc -target x86_64-windows-gnu -O2 -Wall -Wextra -Werror \
  -Wl,--subsystem,windows tools/sdk_launcher.c \
  -o output/current-cs2-tools/game/bin/win64/sdk-launcher.exe
```

The launcher selects `citadel` through the adjacent engine's exported
`Source2Main` function. Run with `-tools -insecure -novid -console -condebug
-playtest`; inspect the mount logs to confirm the selected project. Use an ASCII
workspace path; non-ASCII Windows paths are not validated. This source replaces
an opaque launcher, not the engine's editor or game functionality.

To record editor startup from an interactive Windows desktop, first compile the
model fixture in a Citadel addon, then run:

```sh
python scripts/editor_probe.py --sdk output/current-cs2-tools \
  --reports acceptance/editors --addon model_probe
```

The `--addon` must match the addon used for `compiler_probe.py --kind model`.
The probe records owned window titles, loaded SDK modules and console output,
then closes its own processes. Over Windows SSH, use a temporary Task Scheduler
task with an Interactive principal for the already signed-in desktop account;
the service session cannot supply the editor's DirectX display. The complete
dispatch procedure is reproduced in the accompanying self-contained guide.
Startup checks do not certify map authoring or SFM rendering.

## Inventory the reference

```sh
uv run --no-project python scripts/sdk_inventory.py zip \
  ../modlock-sdk-inputs/Reduced_CSDK_12.zip \
  --strip-prefix Reduced_CSDK_12/ > reference.json
```

`directory <root>` inventories an isolated source tree. `compare <reference>
<source-inventory>...` finds all byte-identical matches, including renamed files,
while leaving unmatched entries explicit. Source acquisition records establish
provenance; hash matches alone do not authenticate a publisher.

## Assemble a reviewed recipe

```sh
uv run --no-project python scripts/assemble_sdk.py recipe.json /path/to/new-sdk
```

A recipe declares `sources` by name, each with a `root`, and a nonempty `files`
array. Each file selects `source`, `from`, `to`, and the expected `sha256`.
Keep the actual Valve app, depot, and manifest with each source declaration.
Configuration replacements can come from a separate reviewed source tree.

Assembly requires a new destination and validates every selected file's hash.
It rejects traversal, duplicate Windows output names, and changed source bytes.
It does not resolve a compiler's dependency set or prove that the result runs.

## Checks

`tests/test_depot_match.py` exercises renamed outputs through the real assembler,
truncated manifests, traversal, changed downloads, and SHA-1 matches whose
SHA-256 differs. The current-toolchain tests cover archive-independent assembly,
empty files, and conflicting depot versions. VPK tests cover preloaded bytes
and truncated directory output. Run with a test deadline:

```sh
uv run python -c 'import subprocess,sys; subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],check=True,timeout=60)'
```
