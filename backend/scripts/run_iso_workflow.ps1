$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# In some PowerShell versions/configs, native stderr can be promoted to
# terminating errors when $ErrorActionPreference='Stop'. Docker emits a
# non-fatal warning on stderr about compose file version; don't let that abort.
try { $PSNativeCommandUseErrorActionPreference = $false } catch {}

# Backend dev server runs on 8001 in this workspace (8000 is often occupied by Docker Desktop).
$base = 'http://127.0.0.1:8001'

function Login([string]$email, [string]$password) {
  $body = @{ email = $email; password = $password } | ConvertTo-Json
  $res = Invoke-RestMethod -Method Post -Uri "${base}/api/v1/auth/login" -ContentType 'application/json' -Body $body
  return $res.access_token
}

Write-Host "1) Health check" -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri "${base}/health"
$health | ConvertTo-Json -Compress | Write-Host

Write-Host "2) Login" -ForegroundColor Cyan
$admin    = Login 'admin@example.com'    'Admin123!'
$issuer   = Login 'mrv@example.com'      'mrv123'
$verifier = Login 'verifier@example.com' 'verifier123'
$approver = Login 'approver@example.com' 'approver123'
Write-Host "Tokens OK" -ForegroundColor Green

Write-Host "3) Fetch a project id from DB" -ForegroundColor Cyan
$oldEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$projectId = (
  docker compose -f "$PSScriptRoot\..\docker-compose.yml" exec -T db psql -U windsurf -d windsurf -q -t -A -c "SELECT id FROM project ORDER BY created_at DESC LIMIT 1;" 2>$null |
    Where-Object { $_ -and $_.Trim() -ne '' } |
    Select-Object -Last 1
).Trim()
$ErrorActionPreference = $oldEap
if (-not $projectId) { throw 'No project found in DB; run seed script first.' }
Write-Host "project_id=$projectId" -ForegroundColor Green

Write-Host "4) Create + activate emission factor (admin)" -ForegroundColor Cyan
$oldEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$existingFactorId = (
  docker compose -f "$PSScriptRoot\..\docker-compose.yml" exec -T db psql -U windsurf -d windsurf -q -t -A -c "SELECT id FROM emission_factor WHERE material_code='CEMENT_OPC' AND version=1 ORDER BY created_at DESC LIMIT 1;" 2>$null |
    Where-Object { $_ -and $_.Trim() -ne '' } |
    Select-Object -Last 1
).Trim()
$ErrorActionPreference = $oldEap

$factorPayload = @{
  material_code = 'CEMENT_OPC'
  material_name = 'Cement (OPC)'
  version = 1
  co2e_per_unit = 0.900000
  unit = 'kg'
  valid_from = '2025-01-01T00:00:00Z'
} | ConvertTo-Json

if ($existingFactorId) {
  $factorId = $existingFactorId
  Write-Host "factor_id=$factorId (existing)" -ForegroundColor Green
} else {
  $factor = Invoke-RestMethod -Method Post -Uri "${base}/api/v1/emission-factors/" -Headers @{ Authorization = "Bearer $admin" } -ContentType 'application/json' -Body $factorPayload
  $factorId = $factor.id
  Write-Host "factor_id=$factorId" -ForegroundColor Green
}

$oldEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$isActive = (
  docker compose -f "$PSScriptRoot\..\docker-compose.yml" exec -T db psql -U windsurf -d windsurf -q -t -A -c "SELECT is_active FROM emission_factor WHERE id='${factorId}' LIMIT 1;" 2>$null |
    Where-Object { $_ -and $_.Trim() -ne '' } |
    Select-Object -Last 1
).Trim().ToLowerInvariant()
$ErrorActionPreference = $oldEap

if ($isActive -eq 't' -or $isActive -eq 'true') {
  Write-Host "factor already active" -ForegroundColor Green
} else {
  try {
    Invoke-RestMethod -Method Post -Uri "${base}/api/v1/emission-factors/$factorId/activate" -Headers @{ Authorization = "Bearer $admin" } -ContentType 'application/json' -Body '{}' | Out-Null
    Write-Host "factor activated" -ForegroundColor Green
  } catch {
    $detail = $null
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
    if (-not $detail) { $detail = $_.Exception.Message }
    Write-Host "factor activation failed: $detail" -ForegroundColor Red
    throw
  }
}

Write-Host "5) Create MRV report (issuer)" -ForegroundColor Cyan
$reportPayload = @{
  project_id = $projectId
  reporting_period = '2025-Q1'
  sample_desc = 'Batch-1 materials + transport'
  parameter = 'scope3_materials'
  value = 'cement_opc'
  total_co2e = 12.345678
  emission_factor_id = $factorId
} | ConvertTo-Json

$report = Invoke-RestMethod -Method Post -Uri "${base}/api/v1/mrv-approval/reports" -Headers @{ Authorization = "Bearer $issuer" } -ContentType 'application/json' -Body $reportPayload
$rid = $report.id
Write-Host "report_id=$rid" -ForegroundColor Green

Write-Host "6) Advance workflow to LOCKED" -ForegroundColor Cyan
Invoke-RestMethod -Method Post -Uri "${base}/api/v1/mrv-approval/reports/$rid/advance" -Headers @{ Authorization = "Bearer $issuer" } -ContentType 'application/json' -Body ('{"next_status":"SUBMITTED"}') | Out-Null
Invoke-RestMethod -Method Post -Uri "${base}/api/v1/mrv-approval/reports/$rid/advance" -Headers @{ Authorization = "Bearer $verifier" } -ContentType 'application/json' -Body ('{"next_status":"VERIFIED"}') | Out-Null
Invoke-RestMethod -Method Post -Uri "${base}/api/v1/mrv-approval/reports/$rid/advance" -Headers @{ Authorization = "Bearer $approver" } -ContentType 'application/json' -Body ('{"next_status":"APPROVED"}') | Out-Null
$locked = Invoke-RestMethod -Method Post -Uri "${base}/api/v1/mrv-approval/reports/$rid/advance" -Headers @{ Authorization = "Bearer $approver" } -ContentType 'application/json' -Body ('{"next_status":"LOCKED"}')

Write-Host "Final report:" -ForegroundColor Cyan
$locked | ConvertTo-Json -Depth 6

Write-Host "DONE" -ForegroundColor Green
