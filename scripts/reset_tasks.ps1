# ============================================================================
# Reset Task Tables Script
# 
# 重新初始化任务相关表格
# 
# 使用方法:
#   .\reset_tasks.ps1 -Mode full      # 完全重置（删除所有任务）
#   .\reset_tasks.ps1 -Mode cleanup   # 仅清理异常任务（推荐）
#   .\reset_tasks.ps1 -Mode dryrun    # 仅查看将要清理的内容
# ============================================================================

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("full", "cleanup", "dryrun")]
    [string]$Mode = "dryrun"
)

# 加载环境变量
$envFile = "..\.env.dev"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value)
        }
    }
}

# 解析 PostgreSQL 连接字符串
$pgUri = $env:POSTGRE_URI
if (-not $pgUri) {
    Write-Error "POSTGRE_URI environment variable not set!"
    exit 1
}

# 解析连接字符串
$uri = [System.Uri]$pgUri
$host = $uri.Host
$port = $uri.Port
$database = $uri.AbsolutePath.TrimStart('/')
$userInfo = $uri.UserInfo.Split(':')
$username = $userInfo[0]
$password = $userInfo[1]

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Task Tables Management" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Mode: $Mode" -ForegroundColor Yellow
Write-Host "Database: $database@$host`:$port" -ForegroundColor Gray
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# 确认操作
if ($Mode -eq "full") {
    Write-Host "WARNING: This will DELETE ALL TASK DATA!" -ForegroundColor Red
    $confirm = Read-Host "Type 'DELETE' to confirm"
    if ($confirm -ne "DELETE") {
        Write-Host "Operation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# 选择 SQL 文件
$sqlFile = switch ($Mode) {
    "full" { "..\sail_server\migration\reset_task_tables.sql" }
    "cleanup" { "..\sail_server\migration\cleanup_abnormal_tasks.sql" }
    "dryrun" { "..\sail_server\migration\cleanup_abnormal_tasks.sql" }
}

# 检查 SQL 文件是否存在
if (-not (Test-Path $sqlFile)) {
    Write-Error "SQL file not found: $sqlFile"
    exit 1
}

# 如果是 dryrun 模式，修改 SQL 文件为只读查询
if ($Mode -eq "dryrun") {
    Write-Host "DRY RUN MODE - Showing what would be cleaned up:" -ForegroundColor Green
    Write-Host ""
    
    # 创建临时 SQL 文件（只包含查询部分）
    $tempSql = @"
-- DRY RUN - Preview only
SELECT 'Current task status summary:' AS info;

SELECT 
    status, 
    COUNT(*) AS task_count,
    MAX(updated_at) AS last_update,
    MIN(created_at) AS oldest_task
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis'
  AND sub_type = 'outline_extraction'
GROUP BY status
ORDER BY task_count DESC;

SELECT 
    'Abnormal tasks that would be cleaned:' AS warning,
    COUNT(*) AS task_count
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis'
  AND sub_type = 'outline_extraction'
  AND (
      status = 'failed'
      OR status = 'cancelled'
      OR (status = 'running' AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes')
      OR status NOT IN ('pending', 'scheduled', 'running', 'paused', 'completed', 'failed', 'cancelled')
  );

SELECT 
    id,
    status,
    current_phase,
    error_message,
    created_at,
    updated_at,
    CASE 
        WHEN status = 'failed' THEN 'Would be cleaned (failed)'
        WHEN status = 'cancelled' THEN 'Would be cleaned (cancelled)'
        WHEN status = 'running' AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes' THEN 'Would be cleaned (stale running)'
        ELSE 'Would be cleaned (abnormal status)'
    END AS cleanup_reason
FROM unified_agent_tasks
WHERE task_type = 'novel_analysis'
  AND sub_type = 'outline_extraction'
  AND (
      status = 'failed'
      OR status = 'cancelled'
      OR (status = 'running' AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes')
      OR status NOT IN ('pending', 'scheduled', 'running', 'paused', 'completed', 'failed', 'cancelled')
  )
ORDER BY id;
"@
    $tempSqlFile = [System.IO.Path]::GetTempFileName() + ".sql"
    $tempSql | Out-File -FilePath $tempSqlFile -Encoding UTF8
    $sqlFile = $tempSqlFile
}

# 执行 SQL
Write-Host "Executing SQL script..." -ForegroundColor Gray
$env:PGPASSWORD = $password

$psqlArgs = @(
    "-h", $host,
    "-p", $port,
    "-U", $username,
    "-d", $database,
    "-f", $sqlFile,
    "-v", "ON_ERROR_STOP=1"
)

try {
    $output = & psql @psqlArgs 2>&1
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Host "===============================================" -ForegroundColor Green
        if ($Mode -eq "dryrun") {
            Write-Host "DRY RUN completed successfully!" -ForegroundColor Green
            Write-Host "No changes were made." -ForegroundColor Yellow
        } else {
            Write-Host "Operation completed successfully!" -ForegroundColor Green
        }
        Write-Host "===============================================" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "===============================================" -ForegroundColor Red
        Write-Host "Operation failed with exit code: $exitCode" -ForegroundColor Red
        Write-Host "===============================================" -ForegroundColor Red
    }
    
    # 显示输出
    if ($output) {
        Write-Host ""
        Write-Host "Output:" -ForegroundColor Gray
        $output | ForEach-Object { Write-Host $_ }
    }
}
catch {
    Write-Error "Failed to execute psql: $_"
    exit 1
}
finally {
    # 清理临时文件
    if ($Mode -eq "dryrun" -and (Test-Path $tempSqlFile)) {
        Remove-Item $tempSqlFile -Force
    }
    
    # 清除密码环境变量
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
