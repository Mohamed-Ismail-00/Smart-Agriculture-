# React Native / Expo mobile build (partial native UI).
# For full web-parity Android app, prefer: .\scripts\build_android_apk.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$MobileDir = Join-Path $Root "packages\mobile"
$SdkDir = $env:ANDROID_HOME
if (-not $SdkDir) { $SdkDir = $env:ANDROID_SDK_ROOT }
if (-not $SdkDir) { $SdkDir = "C:\Users\$env:USERNAME\AppData\Local\Android\Sdk" }

Set-Location $MobileDir
Write-Host "Preparing Android project (Expo prebuild)..."
npx.cmd expo prebuild --clean

Write-Host "Setting up Android SDK location: $SdkDir"
$sdkProp = "sdk.dir=" + ($SdkDir -replace "\\", "/")
Set-Content -Path "android\local.properties" -Value $sdkProp -Encoding ASCII

Write-Host "Building APK using local Android SDK..."
Set-Location android
.\gradlew.bat assembleDebug

Write-Host "Build finished! APK: packages\mobile\android\app\build\outputs\apk\debug\app-debug.apk"
Write-Host "API base: see extra.apiBaseUrl in packages\mobile\app.json"
