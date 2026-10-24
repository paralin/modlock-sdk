# Modlock Tools

**Modlock Tools** builds a Windows toolkit for making [Deadlock] maps, models,
and UI. It runs the Dota 2 Workshop Tools editors (Hammer, ModelDoc, Source
Filmmaker, and the lighting tool) on Deadlock's own engine and resource
compiler, as a content project that loads Deadlock's asset packages and
shaders. Rerunning the installer updates the toolkit to the current Valve
versions.

[Deadlock]: https://store.steampowered.com/app/1422450/Deadlock/

This repository contains the installer, the list of Valve depots and paths the
toolkit uses, a small launcher, a lighting tool wrapper, entity definitions for Hammer, and the scripts
that package and check a release. Valve's binaries and assets come from Steam
at install time. [REPRODUCING.md](REPRODUCING.md) explains how the build works.

> **Early development.** Map compilation passes with baked lighting in
> Deadlock's current layout, and the maps render in Deadlock. The editors moved
> from the CS2 tools to Dota's and are not yet checked on this toolkit; nor are
> Deadlock's materials in the editor viewport, map playtests in Hammer,
> Citadel-specific ModelDoc events, and SFM renders.

## Shaders

Deadlock's engine and resource compiler run with Deadlock's own shaders: its
core shader packages replace the editors' in `game/core`, and its game shader
packages, with `pbr` and `environment_*`, are mounted with its assets. A `pbr`
material compiles as Deadlock compiles it. Dota's and CS2's world shaders are
not part of the toolkit and Deadlock lacks them, so do not use them.

Deadlock's core package is mounted as `game/core_deadlock`, ahead of the
editors' own core, so the engine finds the materials and textures it expects.
The editors' core supplies their interface and tool assets.

## Maps

Build a map from its own source: a new map in Hammer under a name of its own.
Compile its materials, then the map with `-world -phys -vis -bakedlighting
-bakelighting`, as [bundle/README.md](bundle/README.md) shows, and put the
map's VPK together with its compiled materials in one archive, such as with
`modlock vpk pack`. Placed in `game/citadel/maps/`, the archive loads with
`map <name>`.

The compile bakes lighting on the GPU through Vulkan in Deadlock's current
lightmap layout, version 5: the SH2 constant term, one luminance direction
lightmap, and direct light shadows, with light probes and a fog irradiance
volume. Dota's lighting tool writes a direction lightmap for each of red, green
and blue; `vrad3.exe` in the toolkit wraps it, runs it as `vrad3_base.exe`, and
combines the three into the luminance lightmap. Use static lights. A
stationary light needs the precomputed shadow atlas, which the compiler can
only bake with Deadlock's game code loaded, so it lights nothing.

A stock Deadlock map does not recompile into a map Deadlock loads. A map
decompiled with Source 2 Viewer has lost its world node geometry and its
authoring data, and its name and paths collide with the stock map's own files. To change a stock
map, spawn and drive entities on it at runtime instead.

## Install

On Windows, run this in PowerShell:

```powershell
irm https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.ps1 | iex
```

On Linux or macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.sh | bash
```

The installer puts the toolkit in `~/modlock-tools`; set `MODLOCK_TOOLS_DIR` to
choose another directory. It installs [uv] if needed, uses the Dota 2,
Counter-Strike 2 and Deadlock files already in your Steam libraries, and
downloads the rest from Steam with [DepotDownloader]. Downloads need a Steam login: scan the QR code it
prints with the Steam mobile app. Deadlock's asset packages are linked from your
Deadlock installation when the system allows it, and copied otherwise (about 35
GB).

Run the same command again, or `Update.cmd` in the toolkit, to update after a
game update. Only changed files are downloaded, and files Valve removed are
removed. Your addons and edits to the sample addon are kept. Then open
`Hammer.cmd`, `ModelDoc.cmd`, or `SFM.cmd` in the toolkit directory. [bundle/README.md](bundle/README.md)
describes the editors and the sample addon.

[uv]: https://docs.astral.sh/uv/

## Layout

| Path | Contents |
| --- | --- |
| `install.sh`, `install.ps1` | One-line installers that run `scripts/install.py` |
| `profiles/toolkit.json` | The Valve depots the toolkit uses and the paths taken from each |
| `scripts/` | Install, package, and probe scripts (standard library Python) |
| `metadata/` | Entity definitions and the tools `gameinfo.gi` |
| `tools/` | The Windows launcher, the lighting tool wrapper, and the entity metadata exporter |
| `bundle/` | The offline bundle installer and the toolkit README |
| `tests/` | Unit tests for installing and packaging |

## Releases

A release is a tagged source revision; Valve's files are never published. To
install a specific release, set `MODLOCK_TOOLS_REF` to its tag before running
the installer, for example `$env:MODLOCK_TOOLS_REF = '0.0.2'` in PowerShell.

For a machine that cannot reach Steam, pack an installed toolkit into an
offline bundle of ZIPs with a checksum list, and copy it there yourself:

```sh
python3 scripts/release_bundle.py --toolkit ~/modlock-tools \
  --revision "$(git rev-parse HEAD)" --output output/release/$(cat VERSION)
```

[bundle/README.md](bundle/README.md) is the guide copied into each toolkit and
bundle.

## Testing

```sh
python3 -m unittest discover -s tests
```

## Acknowledgments

Modlock Tools reconstructs the community
[CSDK 12](https://deadlockmodding.pages.dev/modding-tools/csdk-12) toolkit,
which Deadlock modding community members built from the Counter-Strike 2
Workshop Tools and their own fixes. Thank you to them and to the Deadlock and
Source 2 modding communities, whose shared tools and research made this
possible. See [ATTRIBUTION.md](ATTRIBUTION.md) for the projects this toolkit
uses.

## License

The scripts, launcher and lighting tool wrapper are MIT licensed. See [LICENSE](LICENSE).
Valve's tools and game content remain Valve's and are not part of this
repository.
