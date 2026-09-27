# Modlock Tools

**Modlock Tools** builds a Windows toolkit for making [Deadlock] maps, models,
and UI. It takes the Counter-Strike 2 Workshop Tools (Hammer, ModelDoc, Source
Filmmaker, and the resource compiler) from Steam and sets them up as a content
project that loads Deadlock's asset packages. Rerunning the installer updates
the toolkit to the current Valve versions.

[Deadlock]: https://store.steampowered.com/app/1422450/Deadlock/

This repository contains the installer, the list of Valve depots and paths the
toolkit uses, a small launcher, entity definitions for Hammer, and the scripts
that package and check a release. Valve's binaries and assets come from Steam
at install time. [REPRODUCING.md](REPRODUCING.md) explains how the build works.

> **Early development.** Hammer, ModelDoc, and SFM start in tools mode on
> native Windows, and model and Panorama compilation pass. Deadlock's own
> materials do not render in the editors; see
> [Shaders](#shaders). Map playtests, Citadel-specific ModelDoc events, and SFM
> renders are not yet validated.

## Shaders

Deadlock and CS2 share an engine but not a shader set, and Deadlock's shader
build is one format version behind CS2's. Most Deadlock materials use
Deadlock's `pbr` and `environment_*` shaders, which the CS2 tools do not have,
so Deadlock's heroes and world show the error material in the editor
viewport. CS2's own world shaders, such as `csgo_complex`, are missing from
Deadlock in turn.

Other compiled formats match: Deadlock's models, textures, particles, sounds,
and Panorama files use the same resource versions as CS2's, and every particle
operator Deadlock defines exists in the CS2 tools. For a material that renders
in both, use a shader the two games share, such as `generic`, `spritecard`
for particles, or `sky`.

## Install

On Windows, run this in PowerShell:

```powershell
irm https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.ps1 | iex
```

On Linux or macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.sh | bash
```

The installer puts the toolkit in `C:\modlock-tools` on Windows and
`~/modlock-tools` elsewhere; set `MODLOCK_TOOLS_DIR` to choose another
directory. It installs [uv] if needed, uses the Counter-Strike 2 and Deadlock
files already in your Steam libraries, and downloads the rest from Steam with
[DepotDownloader]. Downloads need a Steam login: scan the QR code it prints with
the Steam mobile app. Deadlock's asset packages are linked from your Deadlock
installation when the system allows it, and copied otherwise (about 35 GB).

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
| `tools/` | The Windows launcher and the entity metadata exporter |
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

The scripts and launcher are MIT licensed. See [LICENSE](LICENSE).
Valve's tools and game content remain Valve's and are not part of this
repository.
