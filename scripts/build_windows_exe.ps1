param(
    [string]$Python = "python",
    [string]$OutDir  = "dist"
)

$ErrorActionPreference = "Stop"

# ── Resolve version from pyproject.toml ──────────────────────────────────────
$Version = "v0.0.0"
try {
    $RootDir       = Split-Path -Parent $PSScriptRoot
    $PyProjectPath = Join-Path $RootDir "pyproject.toml"
    $PyProject     = Get-Content $PyProjectPath -Raw -ErrorAction Stop
    if ($PyProject -match 'version\s*=\s*"([^"]+)"') {
        $Version = "v$($Matches[1])"
    } else {
        Write-Warning "Could not parse version from pyproject.toml; defaulting to $Version"
    }
} catch {
    Write-Warning "Failed to read pyproject.toml: $_"
}

Write-Host "Building FollowFlow Studio $Version ..." -ForegroundColor Cyan

# ── Install dependencies ──────────────────────────────────────────────────────
& $Python -m pip install --upgrade pip
& $Python -m pip install -e ".[build]"
& $Python -m playwright install chromium --with-deps

# ── PyInstaller build ────────────────────────────────────────────────────────
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "FollowFlow" `
    --paths "src" `
    --collect-all "playwright" `
    --collect-all "customtkinter" `
    "followflow_app.py"

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Build complete: dist\FollowFlow\FollowFlow.exe" -ForegroundColor Green

# ── Create release ZIP inside $OutDir ────────────────────────────────────────
$null = New-Item -ItemType Directory -Force -Path $OutDir
$ZipName = "FollowFlow-Windows-${Version}.zip"
$ZipPath = Join-Path $OutDir $ZipName

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "dist\FollowFlow\*" -DestinationPath $ZipPath

Write-Host "Release archive: $ZipPath" -ForegroundColor Green
