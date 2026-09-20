#!/usr/bin/env python3
"""Download an anonymous Valve manifest or selected files using DepotDownloader."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from depot_match import read_manifest


def download(downloader: Path, app: str, depot: str, manifest: str | None,
             output: Path, filelist: Path | None) -> None:
    """Use a fresh unsigned .NET entry-assembly location and anonymous session.

    The adjacent runtime files must come from a source-built DepotDownloader.
    A new assembly path isolates its .NET account store from previous runs;
    changing the working directory alone does not. Payloads still need recipe
    verification after this operation.
    """
    # Record the tool bytes and isolate account state without changing its source.
    tool_hash = hashlib.sha256(downloader.read_bytes()).hexdigest()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="modlock-depot-") as temporary:
        runtime = Path(temporary) / "runtime"
        shutil.copytree(downloader.parent, runtime)
        destination = output if filelist else Path(temporary) / "manifest"
        arguments = ["dotnet", str(runtime / downloader.name), "-app", app, "-depot", depot,
                     "-os", "windows", "-osarch", "64", "-dir", str(destination)]
        if manifest:
            arguments.extend(["-manifest", manifest])
        if filelist:
            if not filelist.read_text(encoding="utf-8").strip():
                raise ValueError("File list is empty; select matching files first")
            if not manifest:
                raise ValueError("Selected payload downloads require a pinned --manifest")
            arguments.extend(["-filelist", str(filelist.resolve()), "-validate"])
        else:
            arguments.append("-manifest-only")

        # Let Steam own authentication, CDN requests, chunk verification and resume.
        subprocess.run(arguments, check=True)
        receipt = {"app": app, "depot": depot, "manifest": manifest,
                   "os": "windows", "osarch": "64", "login": "anonymous",
                   "acquired_at": datetime.now(timezone.utc).isoformat(),
                   "downloader_sha256": tool_hash}
        if filelist:
            receipt["selection_sha256"] = hashlib.sha256(filelist.read_bytes()).hexdigest()
            receipt["status"] = "download returned; verify payloads before assembly"
            receipt_path = output / f"download_{depot}_{manifest}.json"
        else:
            # Depot access denial can exit zero: require a newly produced manifest.
            dumps = list(destination.glob(f"manifest_{depot}_*.txt"))
            if len(dumps) != 1:
                raise ValueError("Steam returned no unique manifest; check entitlement and requested IDs")
            parsed = read_manifest(dumps[0])
            if parsed.depot != depot or (manifest and parsed.manifest != manifest):
                raise ValueError("Returned manifest IDs differ from the request")
            receipt["manifest"] = parsed.manifest
            receipt["manifest_text_sha256"] = hashlib.sha256(dumps[0].read_bytes()).hexdigest()
            receipt["status"] = "manifest acquired"
            shutil.copyfile(dumps[0], output / dumps[0].name)
            receipt_path = output / dumps[0].with_suffix(".receipt.json").name
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"Acquisition receipt: {receipt_path}")


def main() -> int:
    """Run an anonymous download; report denied access or failed acquisition."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloader", required=True, type=Path, help="Source-built, unsigned DepotDownloader.dll")
    parser.add_argument("--app", required=True)
    parser.add_argument("--depot", required=True)
    parser.add_argument("--manifest", help="Pinned manifest; omission resolves the current public branch")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--filelist", type=Path, help="Selected payload paths; omission downloads only the manifest")
    args = parser.parse_args()
    try:
        download(args.downloader.resolve(), args.app, args.depot, args.manifest, args.output, args.filelist)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"depot_download: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
