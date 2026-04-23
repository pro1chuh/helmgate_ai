param(
    [string]$ReleaseName = "helmgate",
    [string]$Namespace = "default",
    [string]$OpenRouterApiKey = "",
    [string]$GroqApiKey = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$helmCmd = Get-Command helm -ErrorAction SilentlyContinue
if (-not $helmCmd) {
    $fallbackHelm = "C:\Users\dgodo\AppData\Local\Microsoft\WinGet\Packages\Helm.Helm_Microsoft.Winget.Source_8wekyb3d8bbwe\windows-amd64\helm.exe"
    if (Test-Path $fallbackHelm) {
        $helmCmd = @{ Source = $fallbackHelm }
    } else {
        throw "Helm не найден. Установи Helm или открой новый PowerShell после установки."
    }
}

$currentContext = kubectl config current-context 2>$null
if (-not $currentContext) {
    throw "У Kubernetes нет активного context. Включи Kubernetes в Docker Desktop и повтори запуск."
}

Write-Host "Building backend image..." -ForegroundColor Cyan
docker build -t helmgate-backend:local ./backend

Write-Host "Building frontend image..." -ForegroundColor Cyan
docker build -t helmgate-frontend:local ./frontend-demo

Write-Host "Installing/upgrading Helm release..." -ForegroundColor Cyan
& $helmCmd.Source upgrade --install $ReleaseName ./helm/helmgate `
  --namespace $Namespace `
  --create-namespace `
  --set backend.secrets.openrouterApiKey="$OpenRouterApiKey" `
  --set backend.secrets.groqApiKey="$GroqApiKey"

Write-Host ""
Write-Host "Done. Open the UI at http://localhost:30030" -ForegroundColor Green
