param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

& $Python -m pip install -e ".[build]"
& $Python -m playwright install chromium
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

Write-Host ""
Write-Host "Build complete:"
Write-Host "dist\\FollowFlow\\FollowFlow.exe"
