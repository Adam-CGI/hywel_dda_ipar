<#
 .SYNOPSIS
    Applies Azure App Service application settings from a JSON file.

 .DESCRIPTION
    Reads a flat JSON object (key/value) and sets each entry as an App Setting
    using `az webapp config appsettings set`. Secrets should NOT be committed;
    use a local JSON file or a secure pipeline variable source.

 .PARAMETER ResourceGroup
    Azure Resource Group containing the Web App.

 .PARAMETER WebAppName
    Name of the target Azure Web App.

 .PARAMETER SettingsFile
    Path to the JSON file containing settings. Defaults to `flask_app/appsettings.json`.

 .EXAMPLE
    ./scripts/apply_appsettings.ps1 -ResourceGroup RG_xxx -WebAppName app-hdipar-dev -SettingsFile .\local.settings.json

 .NOTES
    - Keys with value `__SET_IN_APP_SETTINGS__` or placeholders are skipped (warning emitted).
    - Large values are supported; Azure CLI handles encoding.
    - Requires Azure CLI logged in: `az login`.
    - For CI, prefer OIDC & federated credentials rather than stored service principal secrets.
#>
param(
    [Parameter(Mandatory = $true)] [string] $ResourceGroup,
    [Parameter(Mandatory = $true)] [string] $WebAppName,
    [string] $SettingsFile = "flask_app/appsettings.json"
)

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI (az) not found. Install from https://aka.ms/azcli."; exit 1
}

if (-not (Test-Path $SettingsFile)) {
    Write-Error "Settings file not found: $SettingsFile"; exit 1
}

Write-Host "Loading settings from $SettingsFile" -ForegroundColor Cyan
$raw = Get-Content -Raw -Path $SettingsFile | ConvertFrom-Json

if (-not $raw) { Write-Error "Failed to parse JSON"; exit 1 }

$pairs = @()
$skipped = @()
foreach ($prop in $raw.PSObject.Properties) {
    $key = $prop.Name
    $value = [string] $prop.Value
    if ($value -match "__SET_IN_APP_SETTINGS__" -or $value -match "<.+>") {
        $skipped += $key
        continue
    }
    $pairs += "$key=$value"
}

if ($pairs.Count -eq 0) {
    Write-Warning "No concrete settings to apply (all placeholders)."; exit 0
}

Write-Host "Applying $($pairs.Count) settings to Web App '$WebAppName' in RG '$ResourceGroup'..." -ForegroundColor Green
az webapp config appsettings set --resource-group $ResourceGroup --name $WebAppName --settings $pairs | Out-Null

Write-Host "App settings updated successfully." -ForegroundColor Green

if ($skipped.Count -gt 0) {
    Write-Warning "Skipped placeholder keys: $($skipped -join ', ')"
}

Write-Host "Tip: Commit only the templated JSON (with placeholders) – never real secrets." -ForegroundColor Yellow