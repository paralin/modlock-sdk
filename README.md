# Modlock Tools

**Modlock Tools** builds a Windows toolkit for making [Deadlock] maps, models,
and UI. It takes the Counter-Strike 2 Workshop Tools (Hammer, ModelDoc, Source
Filmmaker, and the resource compiler) from Steam, adds a content project that
loads Deadlock's asset packages, and packages both as a reproducible release
with checksums.

[Deadlock]: https://store.steampowered.com/app/1422450/Deadlock/

This repository contains file lists, SHA-256 recipes, depot profiles, a small
launcher, and the scripts that download, check, assemble, and package the
toolkit. Valve's binaries and assets come from Steam at build time. A recipe
lists every file in a release with its hash.

> **Early development.** Editor startup, model compilation, and Panorama
> compilation pass on native Windows. Map playtests, Citadel-specific ModelDoc
> events, and SFM renders are not yet validated.

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

Run the same command again to update after a game update. Your addons and edits
to the sample addon are kept. Then open `Hammer.cmd`, `ModelDoc.cmd`, or
`SFM.cmd` in the toolkit directory. [bundle/README.md](bundle/README.md)
describes the editors and the sample addon.

[uv]: https://docs.astral.sh/uv/

## Features

- **Pinned toolchains.** Profiles in [`profiles/`](profiles) pin Valve app,
  depot, and manifest IDs for the CS2 and Dota 2 tools and the Deadlock
  runtime.
- **Verified recipes.** Recipes in [`recipes/`](recipes) map each output path
  to a source file or VPK member and its SHA-256. Assembly stops if any file's
  hash differs.
- **Content project.** `scripts/tool_project.py` writes a Citadel project that
  mounts Deadlock VPKs under the CS2 engine, with an entity definition file
  recovered from shipped maps.
- **Reproducible releases.** `scripts/release_bundle.py` writes deterministic
  ZIPs, `release.json`, and `SHA256SUMS`. `bundle/Install.ps1` verifies every
  archive and installed file before publishing the install directory.
- **Probes.** Compiler and editor probes record which tools work on a given
  machine.

## Layout

| Path | Contents |
| --- | --- |
| `install.sh`, `install.ps1` | One-line installers that run `scripts/install.py` |
| `profiles/` | Pinned Valve app, depot, and manifest selections |
| `recipes/` | Hash-checked file recipes for each assembled tree |
| `manifests/` | Depot file lists, coverage, release manifests, and runtime probe results |
| `metadata/` | Entity definitions and the tools `gameinfo.gi` |
| `scripts/` | Download, match, assemble, probe, and package scripts (standard library Python) |
| `tools/` | The Windows launcher and the entity metadata exporter |
| `bundle/` | The installer and the README shipped in each release |
| `reference/` | Path and hash inventories used as matching references |
| `tests/` | Unit tests for matching, assembly, and packaging |

## Building a release

A release needs Python 3.11 or newer (releases use 3.14.0), the .NET SDK with a
source build of [DepotDownloader], Zig 0.16.0, and a Steam account entitled to
the downloaded apps.

[DepotDownloader]: https://github.com/SteamRE/DepotDownloader

Acquire and assemble the pinned toolchain and Deadlock runtime as described in
[REPRODUCING.md](REPRODUCING.md), then build the launcher and package:

```sh
python3 scripts/build_launcher.py --zig /path/to/zig

python3 scripts/release_bundle.py \
  --tools output/current-cs2-tools \
  --runtime output/current-deadlock \
  --launcher output/authored/sdk-launcher.exe \
  --revision "$(git rev-parse HEAD)" \
  --output output/release/$(cat VERSION)
```

The output folder holds the ZIPs, `Install.ps1`, `release.json`, `README.md`,
and `SHA256SUMS`. [bundle/README.md](bundle/README.md) is the end-user guide
for installing and using a release.

REPRODUCING.md also covers reusing a local Steam installation, reconstructing
the Deadlock content project, and provenance matching against the reference
inventory.

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

The scripts, recipes, and launcher are MIT licensed. See [LICENSE](LICENSE).
Valve's tools and game content remain Valve's and are not part of this
repository.
