# Modlock Tools 0.0.1

A Windows authoring toolkit for exploring Deadlock assets with Hammer, ModelDoc,
and Source Filmmaker. It combines a pinned Valve CS2 toolchain with verified
Deadlock asset packages and a small source-built launcher. It does not contain
the community SDK's executables or modify your Steam installation.

**This is an early developer test release.** Native Windows editor startup,
model compilation, and Panorama compilation pass. Complete map playtests,
Citadel-specific ModelDoc events, and SFM renders still need validation.
The tools use the CS2 engine to author assets; this bundle is not a Deadlock
game client or server.

## What to download

Keep these files together in one download folder:

| File | Purpose |
| --- | --- |
| `modlock-tools-0.0.1-windows-x64.zip` | Editors, compiler, launcher, project configuration, sample addon |
| **Every** `modlock-assets-0.0.1-NNN.zip` | Numbered Deadlock asset parts; all parts listed in `release.json` are required |
| `Install.ps1` and `release.json` | Installer and exact archive/file checksums |
| `README.md` and `SHA256SUMS` | These instructions and download checksums |

The ZIPs are ordinary independent archives, not split-ZIP volumes. Do not
concatenate them. The installer merges their contents into one SDK directory.
Use the complete set from the same release.

## Requirements and installation

- Windows 10 or 11, x64, with a DirectX 11 capable GPU and current drivers.
- A short local path such as `C:\modlock-tools\0.0.1`. Use ASCII characters;
  avoid `%`, `!`, and quotes. Spaces work.
- Allow **80 GB free** when keeping both downloads and the installed SDK.
  The installed files occupy about 37 GB before your own content and caches.
- PowerShell 5.1, included with Windows. Python, .NET SDK, and a compiler are
  needed only to reproduce the bundle from source, not to install or use it.

Open PowerShell in the download folder and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -Destination C:\modlock-tools\0.0.1
```

The installer verifies every ZIP, extracts into a temporary directory, verifies
every installed file, and publishes the completed directory. It refuses an
existing destination so it cannot overwrite your projects. Installation and
verification may take several minutes. Keep the console open until it reports
success. You can remove the downloaded ZIPs afterward if you retain another copy.

If a download is missing or damaged, replace the named archive and rerun. After
an interrupted installation, remove only the abandoned `.modlock-install-*`
directory created beside your chosen destination before retrying.

## Open the tools

From the installed directory, double-click:

- **`Hammer.cmd`** to open the map editor with the `modlock_sample` addon.
- **`ModelDoc.cmd`** to open the editable sample cube, `models/probe.vmdl`.
- **`SFM.cmd`** to open Source Filmmaker and create a session.

Run them on an interactive Windows desktop. An SSH-only session cannot reliably
create the DirectX device. Initial asset discovery can take time. A running
Steam client is not required for the local editor checks; online gameplay
requires the separately installed game and an entitled Steam account.

Edit source files under `content/citadel_addons/modlock_sample/`. Compiled
resources belong under the matching `game/citadel_addons/modlock_sample/`.
Keep both paths paired when creating another addon, then change `-addon` in a
copy of a launcher. Mounted Valve packages live in `game/citadel_assets/`;
keep your changes in your addon.

To force compilation of the included cube, open PowerShell in the installed
directory and run:

```powershell
$sdk = (Get-Location).Path
Push-Location "$sdk\game\bin\win64"
& .\resourcecompiler.exe -game "$sdk\game\citadel" -i "$sdk\content\citadel_addons\modlock_sample\models\probe.vmdl" -nop4 -f
Pop-Location
```

The expected output is
`game/citadel_addons/modlock_sample/models/probe.vmdl_c`. The sample also
includes `panorama/layout/probe.xml` and its JavaScript dependency; compile the
XML with the same command by changing the input path.

## Limits and useful test feedback

The entity definition file supplements Valve's base definitions with 89 classes
observed in shipped maps. It is incomplete: observed properties do not establish
all valid authoring options. Generic models compile; Deadlock-specific animation
events still need schema work. Some assets and preview scenes may have missing
materials or unsupported features under the tools engine. Compiled maps and
assets must be tested separately in Deadlock; successful compilation does not
prove game compatibility.

When reporting a problem, include the tool, action, asset path, visible error,
and `game/citadel/console.log` from that run. Include the bundle version and
`release.json`. For a compiler failure, save its console output too. For the
first test, try opening each editor, compiling the cube, creating and saving a
small map, and saving/reopening an SFM session.

If Windows reports a missing Microsoft runtime DLL, install Microsoft's
[Visual C++ x64 Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
Keep this SDK separate from an existing game installation. To uninstall, first
save your addon sources and sessions elsewhere, then remove the SDK directory.

## Reproduce from source

The source repository's `0.0.1` tag includes pinned depot profiles, per-file
SHA-256 recipes, metadata, launcher source, and packaging/verification scripts.
See [REPRODUCING.md](REPRODUCING.md) in the source checkout for authenticated
Valve acquisition, assembly, native acceptance checks, and release commands.
Archive ordering, timestamps, permissions, compression, and member hashes are
recorded or fixed. `release.json` identifies the source revision, Python/zlib
versions, recipes, and every delivered file.
