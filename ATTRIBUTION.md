# Attribution

Modlock Tools builds on work shared by the Deadlock and Source 2 modding
communities. This file records what the toolkit uses from other projects and
under which terms.

## Valve content

Hammer, ModelDoc, Source Filmmaker, the resource compiler, and every Deadlock
and Counter-Strike 2 asset belong to Valve. This repository contains none of
their binaries or assets. It lists the Valve depots and paths the toolkit uses;
the installer takes those files from the user's own Steam games or downloads
them from Steam. `metadata/citadel.fgd` and `metadata/entity-sources.json` record entity
classes and properties observed in maps shipped with Deadlock.

## Community SDK 12

Modlock Tools reconstructs the community [CSDK
12](https://deadlockmodding.pages.dev/modding-tools/csdk-12) toolkit from
Valve's own downloads. CSDK 12 is the set of Deadlock authoring tools that
Deadlock modding community members assembled by merging the Counter-Strike 2
Workshop Tools with their own fixes, and it defined the layout and workflow
this repository reproduces. Thank you to everyone who built and maintains it.

A path and hash inventory of the community `Reduced_CSDK_12` archive
distributed through that guide served as the reference layout when matching
files to Valve depots. It is kept in the `0.0.1` tag. The repository contains
no files or executables from that archive.

## Tools used at build time

| Project | Use | License |
| --- | --- | --- |
| [DepotDownloader](https://github.com/SteamRE/DepotDownloader) | Downloads the Valve depots that are not installed (`scripts/steam.py`) | GPL-2.0 |
| [ValveResourceFormat](https://github.com/ValveResourceFormat/ValveResourceFormat) | Reads VPKs and entity lumps in `tools/EntityMetadata`; Source2Viewer checks compiled output | MIT |
| [Zig](https://ziglang.org) | Cross-compiles `tools/sdk_launcher.c` | MIT |

These projects are invoked or referenced as separate builds; none of their
source is copied into this repository.
