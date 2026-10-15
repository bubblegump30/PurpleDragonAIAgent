param([string]$Python = 'python', [switch]$Installer)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Build stopped: $Program exited $LASTEXITCODE" }
}
Invoke-Checked $Python @('-c', "import sys; assert sys.platform == 'win32' and sys.version_info >= (3,10) and sys.maxsize > 2**32")
Invoke-Checked $Python @('-m', 'venv', '.build-venv')
$BuildPython = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
Invoke-Checked $BuildPython @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements-build.txt')
Invoke-Checked $BuildPython @('verify_source.py')
Invoke-Checked $BuildPython @('release_check.py')
Invoke-Checked $BuildPython @('verify_windows.py', '--report', 'verification-results\windows-source-build.json')
$ExistingStage = Join-Path $PSScriptRoot 'dist\PurpleDragonAI'
foreach ($RuntimeData in @('config\desktop_preferences.json','config\user_config.json','private-secrets','conversation-data','workspace','logs','config\recovery-backups')) {
    if (Test-Path (Join-Path $ExistingStage $RuntimeData)) { throw 'Build output contains runtime/user data. Move that installation to a safe folder before rebuilding; no data was removed.' }
}
Invoke-Checked $BuildPython @('-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--contents-directory', '.', '--windowed', '--name', 'PurpleDragonAI', '--icon', 'assets\purple_dragon_ai.ico', '--collect-all', 'webview', '--collect-all', 'pythonnet', '--hidden-import', 'webview.platforms.edgechromium', '--add-data', 'frontend:frontend', '--add-data', 'config/default_config.json:config', '--add-data', 'assets:assets', '--add-data', 'plugins:plugins', 'launcher.py')
Invoke-Checked $BuildPython @('-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console', '--name', 'PurpleDragonRecovery', 'recover_settings.py')
$Stage = Join-Path $PSScriptRoot 'dist\PurpleDragonAI'
Copy-Item 'dist\PurpleDragonRecovery.exe' $Stage -Force
Copy-Item 'Verify-Download.ps1','README.md','PLUGIN-API-v1.md','WINDOWS-ACCEPTANCE.md','RELEASE-ACCEPTANCE.md' $Stage -Force
Invoke-Checked $BuildPython @('build_manifest.py', '--root', $Stage, '--distribution', 'windows-onedir')
# Validate the actual frozen runtime's resource paths, config normalization and distribution hashes.
& "$Stage\PurpleDragonRecovery.exe" --check-release
if ($LASTEXITCODE -ne 0) { throw 'Frozen distribution integrity check failed.' }
$Version = (Get-Content 'config\default_config.json' -Raw | ConvertFrom-Json).version
$Archive = Join-Path $PSScriptRoot "dist\PurpleDragonAI-$Version-Windows-x64.zip"
Compress-Archive -Path "$Stage\*" -DestinationPath $Archive -Force
if ($Installer) {
    $Iscc = (Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue).Source
    if (-not $Iscc) { $Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
    if (-not (Test-Path $Iscc)) { throw 'Install Inno Setup 6 and rerun with -Installer. Portable build is available in dist.' }
    Invoke-Checked $Iscc @('/Qp', "installer\PurpleDragonAI.iss")
}
Get-ChildItem dist -File | Where-Object { $_.Extension -in '.zip','.exe' } | ForEach-Object {
    $Hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $($_.Name)" | Set-Content "$($_.FullName).sha256" -Encoding ascii
}
Write-Host 'Unsigned Windows artifacts built. Run actual installation, frozen GUI, upgrade/recovery and uninstall acceptance before public release.'
