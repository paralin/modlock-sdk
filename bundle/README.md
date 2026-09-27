# Modlock Tools

A Windows toolkit for making Deadlock maps, models, and UI with Hammer,
ModelDoc, and Source Filmmaker. It runs Valve's Counter-Strike 2 tools with
Deadlock's asset packages mounted. It edits and compiles assets; it does not
run Deadlock itself.

**Early developer release.** The editors start, and model and Panorama
compilation work on Windows. Deadlock's own materials do not render in the
editors; see Known limits. Map playtests, Deadlock-specific ModelDoc events,
and SFM renders are not yet tested.

## Requirements

- Windows 10 or 11, x64, with a DirectX 11 GPU and current drivers.
- A short ASCII path such as `C:\modlock-tools`, without `%`, `!`, or quotes.
  Spaces work.
- About 40 GB free if Deadlock's packages are copied. When the toolkit is on
  the same drive as Deadlock, the installer links them instead and the toolkit
  needs about 3 GB.

## Install and update

Run this in PowerShell:

```powershell
irm https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.ps1 | iex
```

To update after a game update, run `Update.cmd` in the toolkit. Your addons and
edits to the sample addon are kept.

### From a release download

A release has one `modlock-tools-<version>-windows-x64.zip`, several numbered
`modlock-assets-<version>-NNN.zip` parts, `Install.ps1`, `release.json`, this
README, and `SHA256SUMS`. Download all of them into one folder. Each ZIP is a
separate archive; the installer extracts them all into one directory. Then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -Destination C:\modlock-tools
```

The installer checks every ZIP and every extracted file against `release.json`
before it moves the finished directory into place. It stops if the destination
exists, so it never overwrites your work. If a ZIP is missing or damaged,
download that one again and rerun. After an interrupted install, delete the
`.modlock-install-*` folder next to the destination before retrying.

## Open the tools

Double-click one of these in the toolkit directory:

- `Hammer.cmd` opens the map editor with the `modlock_sample` addon.
- `ModelDoc.cmd` opens the sample cube, `models/probe.vmdl`.
- `SFM.cmd` opens Source Filmmaker.

Run them from a normal Windows desktop session; a remote SSH session cannot
create the DirectX device. The first start takes a while as the tools index the
assets. Steam does not need to be running.

Put addon sources under `content/citadel_addons/<addon>/`. Compiled files go
under the matching `game/citadel_addons/<addon>/`. To work on another addon,
copy a `.cmd` file and change its `-addon` option. Deadlock's packages are in
`game/citadel_assets/`; leave them unchanged and keep your work in your addon.

To compile the sample cube by hand, run this in PowerShell in the toolkit
directory:

```powershell
$sdk = (Get-Location).Path
Push-Location "$sdk\game\bin\win64"
& .\resourcecompiler.exe -game "$sdk\game\citadel" -i "$sdk\content\citadel_addons\modlock_sample\models\probe.vmdl" -nop4 -f
Pop-Location
```

It writes `game/citadel_addons/modlock_sample/models/probe.vmdl_c`. The same
command compiles the sample Panorama layout, `panorama/layout/probe.xml`.

## Known limits

Hammer's entity list adds 89 classes seen in Deadlock's shipped maps to
Valve's base set. It includes only the properties those maps use. ModelDoc has
generic model settings and lacks Deadlock's animation events.

Deadlock and CS2 have different shader sets. Most Deadlock materials use
Deadlock's `pbr` and `environment_*` shaders, which the CS2 tools lack, so
Deadlock's heroes and world show the error material in the viewport. CS2
world shaders such as `csgo_complex` are missing from Deadlock. For a material
that renders in both, use a shared shader such as `generic`, `spritecard`, or
`sky`. Models, textures, particles, sounds, and Panorama files use the same
formats in both games. A file that compiles here may still fail in Deadlock,
so test it in the game.

If Windows reports a missing Microsoft runtime DLL, install the
[Visual C++ x64 Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).

## Reporting a problem

Include the tool, what you did, the asset path, the error you saw, and
`game/citadel/console.log` from that run. For a compiler error, include its
console output.

To uninstall, move your addon sources and SFM sessions elsewhere, then delete
the toolkit directory.

## Source

The source is at <https://github.com/paralin/modlock-sdk>. Its
`REPRODUCING.md` explains how the toolkit is built.
