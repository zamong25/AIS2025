# Windows Task Scheduler 설정 스크립트
# 관리자 권한으로 실행 필요

$taskName = "DelphiTradingSystem"
$scriptPath = "C:\Users\PCW\Desktop\delphi-trader\scripts\run_delphi.bat"
$workingDir = "C:\Users\PCW\Desktop\delphi-trader"

# 기존 작업이 있다면 삭제
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# 트리거 생성 (15분마다, 무한 반복)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)

# 액션 생성
$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $workingDir

# 설정 생성
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# 작업 등록 (시스템 계정으로 실행)
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Settings $settings -RunLevel Highest -User "SYSTEM"

Write-Host "델파이 트레이딩 시스템 스케줄러 설정 완료!"
Write-Host "15분마다 자동 실행됩니다."