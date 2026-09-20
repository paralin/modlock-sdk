<#! Install a verified bundle into a new directory without modifying an existing SDK. #>
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$release = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'release.json') -Raw | ConvertFrom-Json
$target = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Destination)
if (Test-Path -LiteralPath $target) { throw "Destination exists. Choose a new directory: $target" }
if ($target -match '[^\x20-\x7e]|[%!\"]') { throw 'Use a short ASCII path without %, !, or quotes.' }

# Validate every part before consuming space for the extracted SDK.
foreach ($archive in $release.archives) {
    $path = Join-Path $PSScriptRoot $archive.name
    Write-Host "Checking $($archive.name)"
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing archive: $path" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $archive.sha256) {
        throw "Archive checksum mismatch: $path"
    }
}

$parent = Split-Path -Parent $target
[IO.Directory]::CreateDirectory($parent) | Out-Null
$stage = Join-Path $parent ('.modlock-install-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($stage) | Out-Null
try {
    foreach ($archive in $release.archives) {
        Write-Host "Extracting $($archive.name)"
        [IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $PSScriptRoot $archive.name), $stage)
    }
    Write-Host 'Verifying installed files...'
    foreach ($archive in $release.archives) {
        foreach ($member in $archive.members) {
            if ($member.path.EndsWith('/')) { continue }
            $file = Join-Path $stage $member.path
            if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $member.sha256) {
                throw "Installed file checksum mismatch: $($member.path)"
            }
        }
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'release.json') -Destination $stage
    [IO.Directory]::Move($stage, $target)
    Write-Host "Installed Modlock Tools $($release.version) at $target"
    Write-Host 'Open README.md, then run Hammer.cmd, ModelDoc.cmd, or SFM.cmd.'
} finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
