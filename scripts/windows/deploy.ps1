param(
  [string]$Mysql = "mysql",
  [string]$User = "root",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 3306,
  [Alias("DbName")][string]$Database = "office_asset_mgmt",
  [string]$DbPassword,
  [string]$Python = "python",
  [switch]$RunSmokeTest,
  [switch]$Reinitialize,
  [switch]$AdoptExistingBaseline
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$databaseDir = Join-Path $repoRoot "database\bootstrap"
$migrationRunner = Join-Path $repoRoot "tools\migration_runner.py"
$mysqlRunner = Join-Path $repoRoot "tools\run_mysql_utf8.py"

if ($Database -notmatch '^[A-Za-z0-9_]+$') {
  throw "Database must contain only letters, numbers, and underscores."
}
if (-not (Get-Command $Mysql -ErrorAction SilentlyContinue)) {
  throw "MySQL client was not found. Use -Mysql to specify mysql or the full mysql.exe path."
}
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
  throw "Python runtime was not found. Use -Python to specify python or the full executable path."
}
if (-not (Test-Path -LiteralPath $migrationRunner) -or -not (Test-Path -LiteralPath $mysqlRunner)) {
  throw "Deployment tools are incomplete. Run this script from the repository root."
}

if (-not $DbPassword) {
  $secure = Read-Host "MySQL password" -AsSecureString
  $marshal = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $DbPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($marshal)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($marshal)
  }
}

$env:MYSQL_PWD = $DbPassword
$env:DB_PASSWORD = $DbPassword
$env:DB_USER = $User
$env:DB_HOST = $HostName
$env:DB_PORT = "$Port"
$env:DB_NAME = $Database
$env:MYSQL_BIN = $Mysql

function Invoke-MySqlScalar {
  param([string]$Sql)

  $result = & $Mysql `
    --protocol=tcp `
    "--host=$HostName" `
    "--port=$Port" `
    "--user=$User" `
    --default-character-set=utf8mb4 `
    --batch `
    --skip-column-names `
    --silent `
    -e $Sql
  if ($LASTEXITCODE -ne 0) {
    throw "MySQL command failed."
  }
  $lastLine = $result | Select-Object -Last 1
  if ($null -eq $lastLine) {
    return ""
  }
  return $lastLine.ToString().Trim()
}

function Invoke-SqlFile {
  param([string]$FileName)

  $path = Join-Path $databaseDir $FileName
  if (-not (Test-Path -LiteralPath $path)) {
    throw "SQL file not found: $path"
  }

  Write-Host "Applying database/bootstrap/$FileName ..."
  & $Python $mysqlRunner `
    --mysql $Mysql `
    --user $User `
    --host $HostName `
    --port $Port `
    --database $Database `
    --strip-use `
    --file $path
  if ($LASTEXITCODE -ne 0) {
    throw "MySQL failed while applying database/bootstrap/$FileName."
  }
}

Invoke-MySqlScalar "CREATE DATABASE IF NOT EXISTS ``$Database`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" | Out-Null

$coreTableCount = [int](Invoke-MySqlScalar "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$Database' AND table_name IN ('org_unit', 'employee', 'computer_asset');")
$migrationRegistryCount = [int](Invoke-MySqlScalar "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$Database' AND table_name = 'schema_migration';")
$isNewInstallation = $Reinitialize -or $coreTableCount -eq 0

if ($Reinitialize -and $migrationRegistryCount -gt 0) {
  Invoke-MySqlScalar "DROP TABLE IF EXISTS ``$Database``.schema_migration;" | Out-Null
}

if ($isNewInstallation) {
  if ($Reinitialize) {
    Write-Warning "Reinitialize requested: database/bootstrap/01_schema.sql rebuilds tables and removes existing business data."
  }
  Invoke-SqlFile "01_schema.sql"
  Invoke-SqlFile "02_seed_reference_data.sql"

  foreach ($fileName in @(
    "03_views.sql",
    "04_routines.sql",
    "10_audit_log.sql",
    "12_it_inventory.sql",
    "13_hardening_migration.sql",
    "14_computer_configuration.sql",
    "15_inventory_computer_batches.sql",
    "16_inventory_purchase_log.sql",
    "17_data_lineage_and_consistency.sql",
    "18_backfill_computer_inbound_dates.sql",
    "19_auth_and_settings.sql",
    "20_database_backup.sql",
    "21_security_hardening.sql",
    "22_update_repository_setting.sql"
  )) {
    Invoke-SqlFile $fileName
  }

  & $Python $migrationRunner --database $Database --mark-baseline "legacy-20260813"
  if ($LASTEXITCODE -ne 0) {
    throw "Unable to record the historical migration baseline."
  }
} else {
  Write-Host "Existing business tables detected; destructive bootstrap scripts will not run."

  if ($migrationRegistryCount -eq 0) {
    if (-not $AdoptExistingBaseline) {
      throw @"
This database has business tables but no schema_migration registry.
Take and verify a backup, confirm compatibility with legacy-20260813, then run:
  .\deploy.ps1 -Database $Database -AdoptExistingBaseline
Historical initialization SQL will not be executed against existing data.
"@
    }

    $legacyRequiredCount = [int](Invoke-MySqlScalar "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$Database' AND table_name IN ('audit_log', 'it_inventory_brand', 'it_inventory_model', 'user_account', 'database_backup', 'auth_bootstrap_guard');")
    if ($legacyRequiredCount -ne 6) {
      throw "The existing database is not compatible with legacy-20260813 plus security baseline. Restore or complete the legacy upgrade before adoption."
    }

    & $Python $migrationRunner --database $Database --mark-baseline "legacy-20260813"
    if ($LASTEXITCODE -ne 0) {
      throw "Unable to adopt the existing database into the migration registry."
    }
  }
}

& $Python $migrationRunner --database $Database
if ($LASTEXITCODE -ne 0) {
  throw "Tracked migration application failed."
}

if ($RunSmokeTest) {
  Invoke-SqlFile "06_smoke_test.sql"
}

Write-Host "Deployment completed for database '$Database'."
