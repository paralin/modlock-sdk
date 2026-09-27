# How Modlock Tools is built

Most people only need the one-line install in the [README](README.md). This
file explains what the installer does, how a release is made, and where the
toolkit's layout came from.

## What the toolkit contains

The toolkit is the Counter-Strike 2 Workshop Tools (Hammer, ModelDoc, Source
Filmmaker, and the resource compiler) set up as a content project for
Deadlock. It has three parts:

- Valve's CS2 tools, taken from three CS2 depots.
- Deadlock's asset packages, the `pak01_*.vpk` files and map packages, mounted
  as `game/citadel_assets`. Deadlock's game code is left out.
- Files from this repository: the launcher, `gameinfo.gi`, the entity
  definitions, a sample addon, and the `.cmd` shortcuts.

[`profiles/toolkit.json`](profiles/toolkit.json) lists each depot and the path
prefixes taken from it. [`scripts/toolkit.py`](scripts/toolkit.py) maps depot
paths to toolkit paths and lists the files this repository adds.

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
4. Remove the Valve files the last run placed that the current depots no longer
   have. `.cache/installed.json` records the placed files and the depot
   manifest IDs they came from.
5. Build the launcher and write this repository's files. The sample addon is
   written only if it is missing, so your edits to it are kept.

When Valve ships a new version, run the installer again (or `Update.cmd` in
the toolkit) to apply the difference.

[DepotDownloader]: https://github.com/SteamRE/DepotDownloader

## The content project

`game/citadel/gameinfo.gi` comes from
[`metadata/citadel-tools-gameinfo.gi`](metadata/citadel-tools-gameinfo.gi). It
runs the CS2 engine with Deadlock's packages added to the search path. It
mounts both `Game core` and `Mod core`, since the default key bindings need
the second, and `LayeredOnMod core` keeps Valve's render defaults.

Valve does not ship an entity definition file for Deadlock's tools.
[`metadata/citadel.fgd`](metadata/citadel.fgd) adds 89 entity classes found in
201 entity lumps across Deadlock's 185 map packages to Valve's base
definitions. These are the classes and properties the shipped maps use, so
some valid options are missing. To regenerate it, build
`tools/EntityMetadata` against [ValveResourceFormat], run it over every map
package, and merge the result:

```sh
dotnet build tools/EntityMetadata/EntityMetadata.csproj -c Release \
  -p:ValveResourceFormatProject=<ValveResourceFormat checkout>/ValveResourceFormat/ValveResourceFormat.csproj
dotnet tools/EntityMetadata/bin/Release/net10.0/EntityMetadata.dll \
  .tmp/map-entities <toolkit>/game/citadel_assets/maps/*.vpk
python3 scripts/entity_fgd.py .tmp/map-entities \
  --core <toolkit>/game/core --output metadata/citadel.fgd
```

[ValveResourceFormat]: https://github.com/ValveResourceFormat/ValveResourceFormat

## The launcher

[`tools/sdk_launcher.c`](tools/sdk_launcher.c) loads the engine next to it and
calls its `Source2Main` with the `citadel` project. The installer builds it
with Zig 0.16.0. The build strips debug records, which would otherwise embed
details of the build machine, so every host produces the same file. Its
SHA-256 is `04b79688dc315ac893134434ee7ce6d7b8c04613df657b07aec3928c3829e92c`.

## Releases

A release is a set of ZIPs for people who cannot run the installer. To make
one, install the toolkit, then pack it:

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
the sample model or Panorama layout twice and records the output hashes. Run
it on a copy of the toolkit, since it adds a new addon each time:

```sh
python scripts/compiler_probe.py --sdk <toolkit> --mod citadel --kind model \
  --addon model_probe --report reports/model.json
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
The current CS2 tools replace the older binaries, and this repository's
launcher, `gameinfo.gi` and entity definitions replace the community files. No file from the archive is used.

The matching scripts, the hash inventory and the per-file recipes are in the
`0.0.1` tag.
