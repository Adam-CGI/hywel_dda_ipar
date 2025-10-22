<#
Hywel Dda IPAR – Document Miner (MVP)
Delta Provisioning Script without RBAC (single-user Azure access)
Run:
  .\deploy_hdipar_resources.ps1 -SubscriptionId "<YOUR-SUBSCRIPTION-ID>"
#>
<#
Hywel Dda IPAR – Document Miner (MVP)
Delta Provisioning Script (no RBAC). Idempotent. Single-writer logging.
Run:
  .\deploy_hdipar_delta.ps1 -SubscriptionId "<SUB>"
#>

param(
  [Parameter(Mandatory=$true)][string]$SubscriptionId,
  [string]$Location = "uksouth",
  [string]$OpenAiLocation = "westeurope",
  [string]$ResourceGroup = "RG_300000000120926_Hywel_Dda_AI"
)

# ---- names ----
$SA="sthdipardev"
$Search="ais-hdipar-dev"
$AOAI="aoai-hdipar-dev"
$DI="di-hdipar-dev"
$Cosmos="cosmos-hdipar-dev"
$Db="ipar"
$WebPlan="asp-hdipar-dev"
$Web="app-hdipar-dev"
$KV="kv-hdipar-dev"
$LAW="log-hdipar-dev"
$AppI="appi-hdipar-dev"
$IndexName="ipar-chunks"
$EmbName="text-embedding-3-large"

# ---- logging ----
$LogDir = Join-Path $PSScriptRoot "logs"; New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("hdipar_deploy_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
Start-Transcript -Path $LogPath -Append
$ErrorActionPreference = 'Continue'
$env:AZURE_CORE_ONLY_SHOW_ERRORS = "true"

function Wait-Provision {
  param([scriptblock]$Check,[int]$TimeoutSec=600,[int]$SleepSec=8,[string]$What="resource")
  $start = Get-Date
  while ($true) {
    try { & $Check; if ($LASTEXITCODE -eq 0) { return } } catch {}
    if ((Get-Date) - $start -gt [TimeSpan]::FromSeconds($TimeoutSec)) { throw "Timeout waiting for $What" }
    Start-Sleep -Seconds $SleepSec
  }
}

Write-Host "Subscription: $SubscriptionId"
az account set --subscription $SubscriptionId | Out-Null

# ---- RG ----
az group create -n $ResourceGroup -l $Location | Out-Null

# ---- Storage containers (idempotent) ----
@("raw","extracted","thumbs","manifests","archive") | % {
  az storage container create --account-name $SA --name $_ --auth-mode login | Out-Null
}

# ---- Cosmos (serverless) ----
# Create account if missing
az resource show -g $ResourceGroup -n $Cosmos --resource-type "Microsoft.DocumentDB/databaseAccounts" 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  az cosmosdb create -g $ResourceGroup -n $Cosmos -l $Location --capabilities EnableServerless | Out-Null
}
# Wait for account ready
Wait-Provision -What "Cosmos account" -Check {
  az cosmosdb show -g $ResourceGroup -n $Cosmos --query "provisioningState=='Succeeded'" -o tsv 1>$null 2>$null
}
# DB
az cosmosdb sql database show -g $ResourceGroup -a $Cosmos -n $Db 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  az cosmosdb sql database create -g $ResourceGroup -a $Cosmos -n $Db | Out-Null
}
# Containers
@("documents","lineage","events","users") | % {
  az cosmosdb sql container show -g $ResourceGroup -a $Cosmos -d $Db -n $_ 1>$null 2>$null
  if ($LASTEXITCODE -ne 0) {
    az cosmosdb sql container create -g $ResourceGroup -a $Cosmos -d $Db -n $_ --partition-key-path "/id" | Out-Null
  }
}

# ---- Web App (Python 3.11) ----
az resource show -g $ResourceGroup -n $Web --resource-type "Microsoft.Web/sites" 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  az webapp create -g $ResourceGroup -p $WebPlan -n $Web --runtime "PYTHON|3.11" | Out-Null
}

# ---- App Insights setting ----
$Conn = az monitor app-insights component show -g $ResourceGroup -a $AppI --query connectionString -o tsv
if ($Conn) { az webapp config appsettings set -g $ResourceGroup -n $Web --settings APPLICATIONINSIGHTS_CONNECTION_STRING="$Conn" | Out-Null }

# ---- Azure OpenAI embedding deployment ----
az cognitiveservices account deployment show -g $ResourceGroup -n $AOAI --deployment-name $EmbName 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  az cognitiveservices account deployment create `
    -g $ResourceGroup -n $AOAI `
    --deployment-name $EmbName `
    --model-format OpenAI `
    --model-name $EmbName `
    --model-version "latest" `
    --sku-name "Standard" `
    --sku-capacity 1 | Out-Null
}

# ---- Azure AI Search index ----
# Get admin key
$SearchKey = az search admin-key show -g $ResourceGroup -n $Search --query primaryKey -o tsv
# Check index existence
az rest --method get `
  --headers "api-key=$SearchKey" `
  --url "https://$Search.search.windows.net/indexes/$IndexName?api-version=2023-11-01" 1>$null 2>$null
$indexExists = ($LASTEXITCODE -eq 0)

if (-not $indexExists) {
  $IndexSpec = @'
{
  "name": "ipar-chunks",
  "fields": [
    {"name":"id","type":"Edm.String","key":true,"searchable":false},
    {"name":"doc_id","type":"Edm.String","filterable":true,"searchable":false},
    {"name":"logical_id","type":"Edm.String","filterable":true,"searchable":false},
    {"name":"version","type":"Edm.Int32","filterable":true,"sortable":true},
    {"name":"source_uri","type":"Edm.String","filterable":true,"searchable":false},
    {"name":"title","type":"Edm.String","searchable":true},
    {"name":"origin_filename","type":"Edm.String","searchable":true},
    {"name":"page_no","type":"Edm.Int32","filterable":true,"sortable":true},
    {"name":"observed_date","type":"Edm.DateTimeOffset","filterable":true,"sortable":true},
    {"name":"kpi_tags","type":"Collection(Edm.String)","filterable":true,"facetable":true},
    {"name":"text","type":"Edm.String","searchable":true},
    {"name":"spans","type":"Edm.String","searchable":false},
    {"name":"vector","type":"Collection(Edm.Single)","searchable":true,
     "vectorSearchDimensions":3072,"vectorSearchConfiguration":"veconf"}
  ],
  "vectorSearch": {
    "profiles": [{"name":"veconf","algorithm":"hnsw"}],
    "algorithms":[{"name":"hnsw","kind":"hnsw"}]
  }
}
'@
  az rest --method put `
    --headers "api-key=$SearchKey" "Content-Type=application/json" `
    --url "https://$Search.search.windows.net/indexes/$IndexName?api-version=2023-11-01" `
    --body "$IndexSpec" | Out-Null
}

Write-Host "`nDone."
Write-Host "Web App: https://$Web.azurewebsites.net/"
Write-Host "Log file: $LogPath"

Stop-Transcript