# How Modlock Tools is built

Most people only need the one-line install in the [README](README.md). This
file explains what the installer does, how a release is made, and where the
toolkit's layout came from.

## What the toolkit contains

The toolkit runs the Dota 2 Workshop Tools editors on Deadlock's engine, as a
content project for Deadlock. Deadlock's tools ship without editors, and
Dota's are the most recent Valve releases. It has these parts:

- Dota 2's tools from three Dota depots: `game/bin`, the editors' `game/core`,
  and `content/core`. Dota's lighting tool is renamed `vrad3_base.exe`, and
  its library is placed as both `vrad3.dll` and `vrad3_base.dll`: the
  launcher loads the library named after its own file, and the tool loads
  `vrad3.dll`.
- Deadlock's engine, resource compiler and their libraries from
  `game/bin/win64`, which replace Dota's copies, and Deadlock's core shader
  packages, which replace Dota's in `game/core`.
- Deadlock's core package, mounted as `game/core_deadlock`, and its asset
  packages, map packages and game shader packages, mounted as
  `game/citadel_assets`. Deadlock's game code is left out.
- Two texture compression libraries from CS2, `bc7e.dll` and
  `ispc_texcomp.dll`, which Deadlock's compiler loads and neither Deadlock nor
  Dota ships.
- Files from this repository: the launcher, the lighting tool wrapper,
  `gameinfo.gi`, the entity definitions, a sample addon, and the `.cmd`
  shortcuts.

[`profiles/toolkit.json`](profiles/toolkit.json) lists each depot and maps the
depot path prefixes it takes to toolkit paths, or to several for a file needed
under more than one name; the longest matching prefix decides where a file
goes. [`scripts/toolkit.py`](scripts/toolkit.py) applies that map and lists
the files this repository adds.

## Installing and updating

[`scripts/install.py`](scripts/install.py) runs the same steps on a first
install and on every update:

1. Find the depots this machine already has. Steam records each installed
   depot and its manifest ID in `steamapps/appmanifest_<app>.acf`, and keeps
   the manifest in `depotcache/`. The manifest lists every file in the depot,
   so the installer reads the current file list without logging in.
2. Download every other depot with [DepotDownloader]. Each depot gets its own
   folder in `.cache/depots/`, and DepotDownloader fetches only the files that
   changed since the last run. Valve requires a Steam login for these depots.
   The first download shows a QR code for the Steam mobile app; later runs
   reuse the saved login.
3. Place the selected files. Depots are applied in profile order, so a later
   depot's copy of a file replaces an earlier one's. Asset packages are hard
   linked (or symbolically linked) to their source, so they take no extra
   space; other files are copied. A file that already matches is skipped.
   Shader packages are the exception: the editors' asset system reads every
   package in a game directory other than `pak01` as a map, and reports a
   split shader package's `_000` archive as corrupt. The installer writes each
   shader package as one file, its archives' data moved into the index, on
   every run.
4. Remove the Valve files the last run placed that the current depots no longer
   have. `.cache/installed.json` records the placed files and the depot
   manifest IDs they came from, and is marked complete only once everything
   the run wrote is on disk. A run that finds it incomplete, after a crash or
   power loss, checks every downloaded file against Steam's checksums and
   copies every placed file again.
5. Build the launcher and the lighting tool wrapper, and write this
   repository's files. The sample addon is written only if it is missing, so
   your edits to it are kept.

When Valve ships a new version, run the installer again (or `Update.cmd` in
the toolkit) to apply the difference.

[DepotDownloader]: https://github.com/SteamRE/DepotDownloader

## The content project

`game/citadel/gameinfo.gi` comes from
[`metadata/citadel-tools-gameinfo.gi`](metadata/citadel-tools-gameinfo.gi). It
adds Deadlock's packages to the search path, with `core_deadlock` ahead of the
editors' `core`. It mounts both `Game core` and `Mod core`, since the default
key bindings need the second, and `LayeredOnMod core` keeps Valve's render
defaults. Its `ResourceCompiler`, `SceneSystem` and `WorldRenderer` blocks are
Deadlock's own, without the game's post-build steps, whose PvE navigation cache
step crashes without the game's code. `BakedLighting` selects the version 5
lightmap channels; without it a map compile skips the bake and writes no
lightmaps. Its `RenderSystem` block asks Vulkan for descriptor indexing, which
the GPU lighting tool's scene descriptors need. `HasModAppSystems 0` keeps
Deadlock's game code unloaded, which leaves out the precomputed shadow atlas
that stationary lights need.

Valve does not ship an entity definition file for Deadlock's tools.
[`metadata/citadel.fgd`](metadata/citadel.fgd) adds 104 entity classes found in
242 entity lumps across 218 Deadlock map packages to Valve's base definitions.
These are the classes and properties the shipped maps use, so some valid
options are missing. The packages come from more than one game build, so a
class stays available after Valve removes the map that used it.
[`metadata/entity-sources.json`](metadata/entity-sources.json) lists each
package and lump by hash.

To refresh it after a game update, build `tools/EntityMetadata` against
[ValveResourceFormat], run it over the current build's map packages, and merge
the result. The merge keeps every class `citadel.fgd` already declares and every
lump `entity-sources.json` already lists, so it needs no earlier build's maps.

```sh
dotnet build tools/EntityMetadata/EntityMetadata.csproj -c Release \
  -p:ValveResourceFormatProject=<ValveResourceFormat checkout>/ValveResourceFormat/ValveResourceFormat.csproj
dotnet tools/EntityMetadata/bin/Release/net10.0/EntityMetadata.dll \
  .tmp/map-entities $(find <toolkit>/game/citadel_assets/maps -name '*.vpk' | sort)
python3 scripts/entity_fgd.py .tmp/map-entities --core <toolkit>/game/core \
  --output metadata/citadel.fgd --receipt metadata/entity-sources.json
```

[ValveResourceFormat]: https://github.com/ValveResourceFormat/ValveResourceFormat

## The launcher and the lighting tool wrapper

[`tools/sdk_launcher.c`](tools/sdk_launcher.c) loads the engine next to it and
calls its `Source2Main` with the `citadel` project.
The `.cmd` launchers pass `-ignaaw0gjr0`. The editors are Dota's and the
compiler Deadlock's, and their animation libraries disagree on one class,
`CNmSoundEvent`, so the engine's schema check would abort the editors. The
engine looks up the switch that turns that abort into a warning by the
MurmurHash2 of its name (seed `0x31415926`, lowercase, dash included),
`0xd96c98b0`; the switch's real name is unknown, and this one hashes to the
same value.

[`tools/vrad3_shim.c`](tools/vrad3_shim.c) is installed as `vrad3.exe`, where
the resource compiler looks for the lighting tool. Deadlock's compiler writes a
version 5 lighting script, which asks for a luminance direction lightmap that
Dota's lighting tool cannot write. The wrapper rewrites those commands into the
red, green and blue direction lightmaps it can write, runs Dota's tool as
`vrad3_base.exe`, and then combines the three into the luminance lightmap,
weighting each color's direction by its share of the luminance.

[`scripts/build_programs.py`](scripts/build_programs.py) builds both with Zig
0.16.0. The build strips debug records, which would otherwise embed details of
the build machine, so every host produces the same files:

| Program | SHA-256 |
| --- | --- |
| `sdk-launcher.exe` | `04b79688dc315ac893134434ee7ce6d7b8c04613df657b07aec3928c3829e92c` |
| `vrad3.exe` | `39dc1a5ca054897892ba409db3069eca06e108c4f250210fc9570dc64f6bb22e` |

## Offline bundles

An offline bundle is a set of ZIPs for a machine that cannot reach Steam. It
contains Valve's files, so it is for your own machines and is not published.
To make one, install the toolkit, then pack it:

```sh
python3 scripts/release_bundle.py --toolkit ~/modlock-tools \
  --revision "$(git rev-parse HEAD)" --output output/release/$(cat VERSION)
```

The tools and project files go into one ZIP; the asset packages are split
into ZIPs of at most 2 GiB each. `release.json` records the depot manifest IDs,
the source revision, and the SHA-256 of every member. `bundle/Install.ps1`
checks those hashes before it installs. Members are written in a fixed order
with fixed timestamps and permissions, so the same inputs, Python, and zlib
produce the same ZIPs.

## Checking a toolkit

Two scripts check a toolkit on Windows. `scripts/compiler_probe.py` compiles
the sample model, a `pbr` material, or the Panorama layout twice and records the output hashes. Run
it on a copy of the toolkit, since it adds a new addon each time:

```sh
python scripts/compiler_probe.py --sdk <toolkit> --mod citadel --kind model \
  --addon model_probe --report reports/model.json
```

On Linux, the probe runs the compiler through Proton in a new prefix. It needs
a graphical `DISPLAY`, the `proton` script, and the Steam client directory:

```sh
python3 scripts/compiler_probe.py --sdk <toolkit> --mod citadel --kind model \
  --addon model_probe --report reports/model.json \
  --proton "<Steam library>/steamapps/common/Proton - Experimental/proton" \
  --steam ~/.steam/steam
```

`scripts/editor_probe.py` opens Hammer, ModelDoc, and SFM on an interactive
desktop, records their windows, loaded modules and console output, then closes
them. Run it from the signed-in desktop session, since an SSH session cannot
create the editors' DirectX device:

```sh
python scripts/editor_probe.py --sdk <toolkit> --reports reports/editors --addon model_probe
```

## Where the layout came from

The toolkit rebuilds the community
[CSDK 12](https://deadlockmodding.pages.dev/modding-tools/csdk-12) toolkit
from Valve's own depots. To find the layout, we hashed every file in the
community `Reduced_CSDK_12` archive (SHA-256
`b5e2bfa958fcceb7bc2e6f0e9723edc914dcb9dcbfdd9717bca42dde482e93af`) and
searched the CS2 and Deadlock depot manifests for the same files. Valve's
depots supplied 8,064 of its 10,864 files. The others include older Valve
binaries we could not locate, changed configuration, and community additions.
The current Valve tools replace the older binaries, and this repository's
launcher, `gameinfo.gi` and entity definitions replace the community files. No file from the archive is used.

The matching scripts, the hash inventory and the per-file recipes are in the
`0.0.1` tag.
