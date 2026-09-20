# Modlock SDK reconstruction

Reconstruct a toolkit using Valve downloads and explicit, hash-checked file
recipes. Requires Python 3.11+, .NET, and a source build of DepotDownloader.
The Python scripts use only the standard library.

## Current result

The combined verified subset reproduces **2,548 of 10,864 reference paths**,
occupying 702,976,063 bytes, from Valve downloads. All sources use CS2 app `730`.

| Input | Depot | Manifest | Matching output paths |
| --- | --- | --- | ---: |
| Windows libraries: 43 files | 2347771 | 5806169188224907599 | 166 |
| Loose content: 2,120 files | 2347770 | 2053759441494650084 | 2,150 |
| Core VPK: 7 package files, 1,549 members | 2347770 | 2053759441494650084 | 232 |

These are byte-identical available sources, not proof of which depot the
community assembler originally used. Empty files and common libraries can
have many indistinguishable sources. Alternate matches remain in the plans.

This is a dependency subset, **not a runnable SDK**. It contains shared runtime
libraries, Qt plugins, and signatures. Resource Compiler, Hammer, the Citadel
runtime, authored configuration, and community additions remain unresolved.
No community executable has been run or used as an assembly input.

The combined recipe is `recipes/valve-verified-subset.json` and the local
assembly is `output/valve-verified-subset/`. Individual plans and recipes retain
each source. `manifests/coverage.json` counts the remaining 8,316 paths by
directory and extension. `reference/csdk12.json`
contains hashes and paths, not the community binaries. The original archive's
SHA-256 is `b5e2bfa958fcceb7bc2e6f0e9723edc914dcb9dcbfdd9717bca42dde482e93af`.

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

Current CS2 Workshop Tools (`730` / `2347779`) and Deadlock (`1422450`)
denied anonymous access. Use an entitled account interactively in Terminal:

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

After resolving the compiler and its dependency set, run the Panorama compile
probe on Windows x64. Require `.vxml_c` and `.vjs_c` outputs, then test Hammer,
ModelDoc, and S2FM separately. These runtime checks have not run on this Mac.

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
SHA-256 differs. Run with a test deadline:

```sh
uv run python -c 'import subprocess,sys; subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],check=True,timeout=60)'
```
