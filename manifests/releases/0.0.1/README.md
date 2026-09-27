# Modlock Tools 0.0.1 acceptance

The source revision is `b580f29a23ce0636fa7de5ec0a81d6df653fcf4e`.
The release contains 18 ZIPs totaling 20,055,287,987 bytes: one tools archive
and 17 asset archives. They install 3,147 files and five explicit directories.

`release.json` identifies every archive and member by SHA-256. Its own SHA-256
is `d8643f4fc13dc873bfca02cb7e593b5d369fee74292f02b4a61681c8323199db`.
`SHA256SUMS` also covers the installer and developer README. These files record
the build; the Valve binaries and ZIP payloads remain outside Git.

## Windows acceptance

The PowerShell installer completed a full installation. Small independent
fixtures also established that it refuses an existing destination and rejects
a corrupt archive before extraction. `final-members.json` records verification
of every installed member against the final release manifest.

The model and Panorama probes each compiled their source fixture twice with
identical output hashes. Their JSON receipts retain the source, compiler, and
output hashes; raw logs remain in the ignored build output. These compiler inputs
did not change when launcher debug records were stripped for the final bundle.

The actual `Hammer.cmd`, `ModelDoc.cmd`, and `SFM.cmd` entry points opened their
expected editor windows using the final launcher. Hammer and SFM closed cleanly.
The first automated ModelDoc close check timed out; the follow-up established
that ModelDoc was displaying its **Compile?** prompt for the sample source.
The bounded test then stopped only its own process tree. Both observations are
preserved in `launchers/` and `modeldoc-close/`; the initial close timeout is not
silently presented as a clean shutdown.

This establishes installation, editor startup, and asset compilation. Complete
map authoring/playtests, Citadel-specific animation events, and SFM renders are
not established by these checks.

## Independent reconstruction

The second machine's Steam installation supplied 2,358 matching CS2 tools files
and all 461 Deadlock asset VPKs. DepotDownloader built from revision
`e7474cb9ee8a87c0d917489b84c75667a1364aa1` downloaded the pinned Workshop Tools
depot directly from Valve after interactive authentication. Its 315 selected
files completed the tools recipe. This includes `csgo.signatures`, for which
the installed game's copy differs from the required Workshop Tools copy.

The launcher was compiled locally from source with Zig 0.16.0. Stripping debug
records produces identical executable bytes on macOS and Linux:
`04b79688dc315ac893134434ee7ce6d7b8c04613df657b07aec3928c3829e92c`.
Both archive builders use Windows Python 3.14.0 and zlib `1.3.1.zlib-ng`.

The independent build produced the same complete `release.json`, including all
18 archive SHA-256 values, as the first build. `independent-build.json` records
the comparison. No assembled SDK binaries were transferred to the second machine.
The native installer verified all 3,147 files before publishing the SDK. Both
compiler probes passed on the second machine, and their compiled outputs also
match the first machine byte-for-byte. `independent-install/` retains these
receipts and the comparison.

For a WSL checkout, stage the completed release directory on a Windows drive
before running `Install.ps1`. Windows hashing over the WSL share was much slower
than reading the same ZIPs locally. The temporary Windows copies can be removed
after installation; the canonical archives remain in the ignored repository
output directory.
