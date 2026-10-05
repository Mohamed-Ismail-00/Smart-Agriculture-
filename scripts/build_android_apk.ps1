# Build AgriData Egypt Android APK (Capacitor + Android SDK)
# Connects to: VITE_API_BASE_URL in services/frontend/web/.env.production
#
# Prerequisites:
#   - Node.js / npm
#   - Android SDK (ANDROID_HOME or local.properties)
#   - Java 17+ (Gradle)
#
# Usage (from repo root):
#   .\scripts\build_android_apk.ps1
#   .\scripts\build_android_apk.ps1 -Release

param(
  [switch]$Release,
  [switch]$OpenStudio
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WebDir = Join-Path $Root "services\frontend\web"
$AndroidDir = Join-Path $WebDir "android"
$SdkDir = $env:ANDROID_HOME
if (-not $SdkDir) { $SdkDir = $env:ANDROID_SDK_ROOT }
if (-not $SdkDir) { $SdkDir = "C:\Users\$env:USERNAME\AppData\Local\Android\Sdk" }

Write-Host "==> Web dir: $WebDir"
Write-Host "==> Android SDK: $SdkDir"

if (-not (Test-Path $SdkDir)) {
  throw "Android SDK not found at $SdkDir. Install Android Studio / SDK and retry."
}

# Point Gradle at the SDK
$localProps = Join-Path $AndroidDir "local.properties"
$sdkProp = "sdk.dir=" + ($SdkDir -replace "\\", "/")
Set-Content -Path $localProps -Value $sdkProp -Encoding ASCII

Push-Location $WebDir
try {
  Write-Host "`n==> Building production web bundle..."
  npm.cmd run build
  if ($LASTEXITCODE -ne 0) { throw "vite build failed" }

  Write-Host "`n==> Syncing Capacitor Android project..."
  npx.cmd cap sync android
  if ($LASTEXITCODE -ne 0) { throw "cap sync failed" }

  Push-Location $AndroidDir
  try {
    if ($Release) {
      Write-Host "`n==> Building RELEASE APK..."
      .\gradlew.bat clean assembleRelease --no-daemon
      $apk = Join-Path $AndroidDir "app\build\outputs\apk\release\app-release.apk"
    } else {
      Write-Host "`n==> Building DEBUG APK..."
      .\gradlew.bat clean assembleDebug --no-daemon
      $apk = Join-Path $AndroidDir "app\build\outputs\apk\debug\app-debug.apk"
    }
    if ($LASTEXITCODE -ne 0) { throw "gradle build failed" }

    if (-not (Test-Path $apk)) { throw "APK not found at $apk" }
    $sizeMb = [math]::Round((Get-Item $apk).Length / 1MB, 2)
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host " BUILD SUCCESS" -ForegroundColor Green
    Write-Host " APK: $apk" -ForegroundColor Green
    Write-Host " Size: ${sizeMb} MB" -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Green

    if ($OpenStudio) {
      Write-Host "Opening Android Studio..."
      npx.cmd cap open android
    }
  } finally {
    Pop-Location
  }
} finally {
  Pop-Location
}
