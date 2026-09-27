# Install or update Modlock Tools:
#   irm https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.ps1 | iex
# Set $env:MODLOCK_TOOLS_DIR to choose the directory (default ~\modlock-tools).
& {
  $ErrorActionPreference = 'Stop'
  # Invoke-WebRequest draws progress so slowly in Windows PowerShell 5.1 that it
  # dominates the download time.
  $ProgressPreference = 'SilentlyContinue'
  $destination = if ($env:MODLOCK_TOOLS_DIR) { $env:MODLOCK_TOOLS_DIR } else { Join-Path $HOME 'modlock-tools' }
  $ref = if ($env:MODLOCK_TOOLS_REF) { $env:MODLOCK_TOOLS_REF } else { 'master' }
  $cache = Join-Path $destination '.cache'
  $source = Join-Path $cache 'source'

  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
  }

  # GitHub archives hold one top-level folder; move it to a fixed path.
  $unpacked = Join-Path $cache 'source-unpacked'
  foreach ($path in $source, $unpacked) {
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
  }
  New-Item -ItemType Directory -Force $cache | Out-Null
  $archive = Join-Path $cache 'source.zip'
  Invoke-WebRequest "https://github.com/paralin/modlock-sdk/archive/$ref.zip" -OutFile $archive
  Expand-Archive $archive $unpacked
  Move-Item (Get-ChildItem $unpacked | Select-Object -First 1).FullName $source
  Remove-Item -Recurse -Force $unpacked, $archive

  uv run --no-project --python 3.14 (Join-Path $source 'scripts\install.py') --destination $destination
  if ($LASTEXITCODE -ne 0) { throw "Modlock Tools installation failed ($LASTEXITCODE)" }
}
