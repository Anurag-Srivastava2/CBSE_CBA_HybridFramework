Write-Host "Checking Allure CLI..." -ForegroundColor Cyan

$allureCommand = Get-Command allure -ErrorAction SilentlyContinue
if ($allureCommand) {
    Write-Host "Allure CLI is already installed: $($allureCommand.Source)" -ForegroundColor Green
    allure --version
    exit 0
}

$npmCommand = Get-Command npm -ErrorAction SilentlyContinue
$npmPath = $null

if ($npmCommand) {
    $npmPath = $npmCommand.Source
}
elseif (Test-Path "C:\Program Files\nodejs\npm.cmd") {
    $npmPath = "C:\Program Files\nodejs\npm.cmd"
}
elseif (Test-Path "$env:APPDATA\npm\npm.cmd") {
    $npmPath = "$env:APPDATA\npm\npm.cmd"
}

if (-not $npmPath) {
    Write-Host "npm was not found in PATH." -ForegroundColor Yellow
    Write-Host "Node.js may be installed, but npm.cmd is not available to this terminal." -ForegroundColor Yellow
    Write-Host "Try closing and reopening VS Code/PowerShell, then run this script again." -ForegroundColor Yellow
    Write-Host "If it still fails, reinstall Node.js from:" -ForegroundColor Yellow
    Write-Host "https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing Allure CLI globally with npm..." -ForegroundColor Cyan
& $npmPath install -g allure-commandline --save-dev

$allureCommand = Get-Command allure -ErrorAction SilentlyContinue
if (-not $allureCommand) {
    Write-Host "Allure installed, but the allure command is still not in PATH." -ForegroundColor Yellow
    Write-Host "Close and reopen the terminal, then run: allure --version" -ForegroundColor Yellow
    exit 1
}

Write-Host "Allure CLI installed successfully: $($allureCommand.Source)" -ForegroundColor Green
allure --version
