# Build pipeline: PyInstaller bundle + Inno Setup installer.
# Run from the project root:  powershell -ExecutionPolicy Bypass -File installer\build.ps1

$ErrorActionPreference = "Stop"

$venv = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venv)) {
    $venv = "python"
}

Write-Host "[1/2] PyInstaller -> dist\VoiceAssistant"
& $venv -m PyInstaller "installer\app.spec" --noconfirm --clean
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Locate Inno Setup compiler (ISCC.exe)
$iscc = Get-ChildItem "C:\Program Files (x86)\Inno Setup*\ISCC.exe",
                       "C:\Program Files\Inno Setup*\ISCC.exe",
                       "$env:LOCALAPPDATA\Programs\Inno Setup*\ISCC.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
if (-not $iscc) {
    $isccCmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($isccCmd) { $iscc = $isccCmd.Source }
}

if (-not $iscc) {
    Write-Warning "ISCC.exe nao encontrado. Build PyInstaller OK; instale Inno Setup para gerar o instalador."
    exit 0
}

$isccPath = if ($iscc -is [System.IO.FileInfo]) { $iscc.FullName } else { [string]$iscc }

Write-Host "[2/2] Inno Setup -> installer\output\VoiceAssistantSetup.exe"
& $isccPath "installer\setup.iss"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Pronto: installer\output\VoiceAssistantSetup.exe"
