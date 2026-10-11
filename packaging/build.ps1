# Builds the Python engine (dist\elissa-engine, PyInstaller) and the Windows installer
# (desktop\src-tauri\target\release\bundle\nsis\Elissa_<version>_x64-setup.exe, Tauri + NSIS), then copies the
# installer to dist\Elissa-Setup-<version>.exe.
# Usage (from anywhere):  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# Needs: uv, Node 22 and Rust (rustup). Set TAURI_SIGNING_PRIVATE_KEY(_PASSWORD) to also sign the update files.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$version = (Select-String -Path 'elissa\__init__.py' -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
$conf = Get-Content 'desktop\src-tauri\tauri.conf.json' -Raw | ConvertFrom-Json
if ($conf.version -ne $version) { throw "Version mismatch: elissa $version vs tauri.conf.json $($conf.version)" }
$parts = ($version.Split('.') + @('0', '0', '0'))[0..3] -join ', '
$vi = Get-Content 'packaging\version_info.txt' -Raw
$vi = $vi -replace 'filevers=\([^)]*\)', "filevers=($parts)" -replace 'prodvers=\([^)]*\)', "prodvers=($parts)"
$vi = $vi -replace "'(File|Product)Version', '[^']*'", "'`$1Version', '$version'"
Set-Content 'packaging\version_info.txt' $vi -Encoding utf8
Write-Host "Elissa $version"

uv sync --frozen
uv run pyinstaller packaging\elissa.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE) { throw 'PyInstaller failed' }

# Update files are signed with the key from `npx tauri signer generate` (kept outside the repo); CI passes it as
# secrets instead.
$keyFile = "$env:USERPROFILE\.tauri\elissa-updater.key"
if (-not $env:TAURI_SIGNING_PRIVATE_KEY -and (Test-Path $keyFile)) {
    $env:TAURI_SIGNING_PRIVATE_KEY = Get-Content $keyFile -Raw
    $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = uv run --no-project --with keyring python -c `
        "import keyring; print(keyring.get_password('Elissa-build', 'updater-key-password') or '')"
}

Push-Location desktop
try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE) { throw 'npm ci failed' }
    npx tauri build
    if ($LASTEXITCODE) { throw 'tauri build failed' }
} finally {
    Pop-Location
}

$setup = Get-Item "desktop\src-tauri\target\release\bundle\nsis\Elissa_${version}_x64-setup.exe"
Copy-Item $setup "dist\Elissa-Setup-$version.exe" -Force
Get-Item "dist\Elissa-Setup-$version.exe" | Select-Object Name, @{n = 'MB'; e = { [math]::Round($_.Length / 1MB, 1) } }
