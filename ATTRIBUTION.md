# Attribution

Modlock Tools builds on work shared by the Deadlock and Source 2 modding
communities. This file records what the toolkit uses from other projects and
under which terms.

## Valve content

Hammer, ModelDoc, Source Filmmaker, the resource compiler, and every Deadlock
and Counter-Strike 2 asset belong to Valve. This repository contains none of
their binaries or assets. It holds file lists, hashes, and recipes that select
files from Valve's own Steam depots or an existing installation on the user's
machine. `metadata/citadel.fgd` and `metadata/entity-sources.json` record entity
classes and properties observed in maps shipped with Deadlock.

## Community SDK 12

`reference/csdk12.json` is a path and hash inventory of the community
`Reduced_CSDK_12` archive distributed through the
[Deadlock modding guide](https://deadlockmodding.pages.dev/modding-tools/csdk-12).
It served as the reference layout when matching files to Valve depots. The
repository contains no files or executables from that archive.

## Tools used at build time

| Project | Use | License |
| --- | --- | --- |
| [DepotDownloader](https://github.com/SteamRE/DepotDownloader) | Downloads pinned Valve depot manifests and files (`scripts/depot_download.py`) | GPL-2.0 |
| [ValveResourceFormat](https://github.com/ValveResourceFormat/ValveResourceFormat) | Reads VPKs and entity lumps in `tools/EntityMetadata`; Source2Viewer checks compiled output | MIT |
| [Zig](https://ziglang.org) | Cross-compiles `tools/sdk_launcher.c` reproducibly | MIT |

These projects are invoked or referenced as separate builds; none of their
source is copied into this repository.
