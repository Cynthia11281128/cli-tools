$ErrorActionPreference = "Stop"
$CliArgs = @($args)

$Script:Version = "windows-native-0.1"
$Script:Root = Join-Path $env:LOCALAPPDATA "cli-tools"
$Script:PortCacheDir = Join-Path $Script:Root "ports"
$Script:LogDir = Join-Path $Script:PortCacheDir "logs"
$Script:RunDir = Join-Path $Script:PortCacheDir "runs"
$Script:RegistryPath = Join-Path $Script:PortCacheDir "registry.json"
$Script:LockPath = Join-Path $Script:PortCacheDir "registry.lock"

function Die([string]$Message) {
    [Console]::Error.WriteLine("error: $Message")
    exit 1
}

function Warn([string]$Message) {
    [Console]::Error.WriteLine("warning: $Message")
}

function Ensure-PortDirs {
    New-Item -ItemType Directory -Force -Path $Script:LogDir, $Script:RunDir | Out-Null
}

function With-PortLock([scriptblock]$Body) {
    Ensure-PortDirs
    $stream = $null
    $deadline = (Get-Date).AddSeconds(5)
    while ($null -eq $stream) {
        try {
            $stream = [System.IO.File]::Open($Script:LockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        } catch {
            if ((Get-Date) -gt $deadline) {
                Die "failed to acquire port registry lock: $Script:LockPath"
            }
            Start-Sleep -Milliseconds 100
        }
    }
    try {
        & $Body
    } finally {
        if ($stream) { $stream.Dispose() }
    }
}

function Validate-Name([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { Die "name is required" }
    if ($Name -notmatch '^[A-Za-z0-9._-]+$') {
        Die "invalid name: $Name; use only letters, numbers, '.', '_', and '-'"
    }
}

function Validate-Port([string]$Port) {
    if ($Port -notmatch '^[0-9]+$') {
        Die "invalid port: $Port; expected an integer from 1 to 65535"
    }
    $n = [int]$Port
    if ($n -lt 1 -or $n -gt 65535) {
        Die "invalid port: $Port; expected an integer from 1 to 65535"
    }
}

function Is-ProcessAlive([int]$ProcId) {
    if ($ProcId -le 0) { return $false }
    $p = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
    return $null -ne $p
}

function Is-PortListening([int]$Port) {
    try {
        $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        foreach ($listener in $listeners) {
            if ($listener.Port -eq $Port) { return $true }
        }
    } catch {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
            $ok = $async.AsyncWaitHandle.WaitOne(120)
            if ($ok) {
                $client.EndConnect($async)
                $client.Close()
                return $true
            }
            $client.Close()
        } catch {
            return $false
        }
    }
    return $false
}

function Is-PortFree([int]$Port) {
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

function Read-RegistryRaw {
    Ensure-PortDirs
    if (!(Test-Path -LiteralPath $Script:RegistryPath)) { return @() }
    $text = Get-Content -LiteralPath $Script:RegistryPath -Raw -ErrorAction SilentlyContinue
    if ([string]::IsNullOrWhiteSpace($text)) { return @() }
    $items = $text | ConvertFrom-Json
    if ($null -eq $items) { return @() }
    if ($items -is [array]) { return @($items) }
    return @($items)
}

function Write-RegistryRaw([array]$Entries) {
    Ensure-PortDirs
    @($Entries) | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Script:RegistryPath -Encoding UTF8
}

function Cleanup-Stale([array]$Entries) {
    $active = @()
    foreach ($entry in $Entries) {
        if ($null -eq $entry.Pid) { continue }
        if (Is-ProcessAlive ([int]$entry.Pid)) {
            $active += $entry
        }
    }
    return $active
}

function Read-Registry {
    $entries = Read-RegistryRaw
    $active = Cleanup-Stale $entries
    if ($active.Count -ne $entries.Count) {
        Write-RegistryRaw $active
    }
    return @($active)
}

function Find-ByName([array]$Entries, [string]$Name) {
    foreach ($entry in $Entries) {
        if ($entry.Name -eq $Name) { return $entry }
    }
    return $null
}

function Find-ByPort([array]$Entries, [int]$Port) {
    foreach ($entry in $Entries) {
        if ([int]$entry.Port -eq $Port) { return $entry }
    }
    return $null
}

function Entry-ForTarget([array]$Entries, [string]$Target) {
    if ($Target -match '^[0-9]+$') {
        $n = [int]$Target
        if ($n -ge 1 -and $n -le 65535) {
            $byPort = Find-ByPort $Entries $n
            if ($byPort) { return $byPort }
        }
    }
    Validate-Name $Target
    $byName = Find-ByName $Entries $Target
    if ($byName) { return $byName }
    Die "unknown named port service: $Target"
}

function Format-CommandText([string[]]$Command) {
    $parts = @()
    foreach ($arg in $Command) {
        if ($arg -match '^[A-Za-z0-9_./:=@,+-]+$') {
            $parts += $arg
        } else {
            $parts += "'" + ($arg -replace "'", "''") + "'"
        }
    }
    return ($parts -join " ")
}

function Validate-Command([string[]]$Command) {
    if ($Command.Count -eq 0 -or [string]::IsNullOrWhiteSpace($Command[0])) {
        Die "missing command to run"
    }
    $cmd = $Command[0]
    $isPathLike = $cmd.Contains("\") -or $cmd.Contains("/") -or ($cmd -match '^[A-Za-z]:')
    if ($isPathLike) {
        if (!(Test-Path -LiteralPath $cmd -PathType Leaf)) {
            Die "command is not executable: $cmd"
        }
        return
    }
    $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($null -eq $resolved) {
        Die "missing command: $cmd"
    }
}

function Find-AvailablePort([int]$Start, [array]$Entries) {
    for ($p = $Start; $p -le 65535; $p++) {
        if (Find-ByPort $Entries $p) { continue }
        if (!(Is-PortFree $p)) { continue }
        return $p
    }
    Die "failed to find an available port from $Start to 65535"
}

function New-RunnerScript([string]$ServiceDir) {
    $runner = @'
param([string]$ConfigPath)
$ErrorActionPreference = "Stop"
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
Set-Location -LiteralPath $config.Cwd
$env:PORT = [string]$config.Port
foreach ($item in @($config.Env.PSObject.Properties)) {
    Set-Item -Path ("Env:" + $item.Name) -Value ([string]$item.Value)
}
$cmd = [string]$config.Command[0]
$cmdArgs = @()
if ($config.Command.Count -gt 1) {
    $cmdArgs = @($config.Command | Select-Object -Skip 1)
}
try {
    & $cmd @cmdArgs *>> $config.LogPath
    if ($null -ne $global:LASTEXITCODE) { exit $global:LASTEXITCODE }
    exit 0
} catch {
    $_ | Out-String | Add-Content -LiteralPath $config.LogPath
    exit 1
}
'@
    $path = Join-Path $ServiceDir "run.ps1"
    Set-Content -LiteralPath $path -Value $runner -Encoding UTF8
    return $path
}

function Start-ServiceEntry([string]$Name, [int]$Port, [string[]]$Command, [string]$Cwd) {
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $startTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $safeName = $Name -replace '[^A-Za-z0-9._-]', '_'
    $serviceDir = Join-Path $Script:RunDir "$safeName-$Port-$timestamp"
    New-Item -ItemType Directory -Force -Path $serviceDir | Out-Null
    $logPath = Join-Path $Script:LogDir "$safeName-$Port-$timestamp.log"
    New-Item -ItemType File -Force -Path $logPath | Out-Null

    $runner = New-RunnerScript $serviceDir
    $configPath = Join-Path $serviceDir "config.json"
    $config = [pscustomobject]@{
        Name = $Name
        Port = $Port
        Command = @($Command)
        Cwd = $Cwd
        LogPath = $logPath
        Env = @{}
    }
    $config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8

    $ps = (Get-Command powershell.exe -ErrorAction Stop).Source
    $proc = Start-Process -FilePath $ps -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $runner, "-ConfigPath", $configPath) -WindowStyle Hidden -PassThru -WorkingDirectory $Cwd

    $status = "running, but port is not listening yet"
    for ($i = 0; $i -lt 50; $i++) {
        Start-Sleep -Milliseconds 100
        if (!(Is-ProcessAlive $proc.Id) -and !(Is-PortListening $Port)) {
            Die "command exited before port $Port started; log: $logPath"
        }
        if (Is-PortListening $Port) {
            $status = "listening"
            break
        }
    }

    return [pscustomobject]@{
        Name = $Name
        Port = $Port
        Pid = $proc.Id
        StartTime = $startTime
        LogPath = $logPath
        Command = @($Command)
        CommandText = (Format-CommandText $Command)
        Cwd = $Cwd
        Status = $status
    }
}

function Stop-ServiceEntry([object]$Entry) {
    if (!(Is-ProcessAlive ([int]$Entry.Pid))) {
        Write-Host "Removed stale named port service: $($Entry.Name)"
        return
    }
    Write-Host "Stopping named port service: $($Entry.Name)"
    Write-Host "  port: $($Entry.Port)"
    Write-Host "  pid: $($Entry.Pid)"
    & taskkill.exe /PID ([string]$Entry.Pid) /T /F | Out-Null
    Write-Host "Stopped named port service: $($Entry.Name)"
}

function Show-MainUsage {
@"
Usage:
  cli-tools
  cli-tools list
  cli-tools help
  cli-tools command [args...]

List or run commands from this Windows-native cli-tools installation.
"@ | Write-Host
}

function Show-PortStartUsage {
@"
Usage:
  cli-tools port-start [name] [port|auto] [options] -- <command> [args...]

Start a long-running command in the background, name it, and remember the port.

Environment options:
  --name NAME    Use NAME instead of prompting when the positional name is omitted.
  --port PORT    Use PORT instead of auto-selecting a port.
  --env ENV      Run through: conda run --no-capture-output -n ENV ...
  --no-env       Run the command as-is.
  --ask-env      Prompt for a conda environment.
"@ | Write-Host
}

function Cmd-List([string[]]$CommandArgs) {
    if ($CommandArgs.Count -gt 0 -and ($CommandArgs[0] -eq "-h" -or $CommandArgs[0] -eq "--help")) {
@"
Usage:
  cli-tools list

List available Windows-native cli-tools subcommands.
"@ | Write-Host
        return
    }
    if ($CommandArgs.Count -ne 0) { Die "this command does not accept arguments" }
    Write-Host "Available cli-tools subcommands:"
    @(
        "list",
        "port-clear-cache",
        "port-list",
        "port-rename",
        "port-restart",
        "port-start",
        "port-stop"
    ) | ForEach-Object { Write-Host "  $_" }
}

function Cmd-PortStart([string[]]$CommandArgs) {
    if ($CommandArgs.Count -gt 0 -and ($CommandArgs[0] -eq "-h" -or $CommandArgs[0] -eq "--help")) {
        Show-PortStartUsage
        return
    }
    if ($CommandArgs.Count -lt 1) {
        Show-PortStartUsage
        Die "expected [name] [port|auto] -- <command> [args...]"
    }

    $name = ""
    $port = ""
    $autoPort = $true
    $envMode = "auto"
    $envName = ""
    $i = 0

    if ($i -lt $CommandArgs.Count -and $CommandArgs[$i] -ne "--" -and !$CommandArgs[$i].StartsWith("--")) {
        $name = $CommandArgs[$i]
        $i++
    }

    if ($i -lt $CommandArgs.Count -and $CommandArgs[$i] -ne "--" -and !$CommandArgs[$i].StartsWith("--")) {
        if ($CommandArgs[$i] -eq "auto") {
            $autoPort = $true
            $i++
        } elseif ($CommandArgs[$i] -match '^[0-9]+$') {
            $port = $CommandArgs[$i]
            $autoPort = $false
            $i++
        } else {
            Show-PortStartUsage
            Die "invalid port: $($CommandArgs[$i]); use an integer, auto, or omit it"
        }
    }

    while ($i -lt $CommandArgs.Count -and $CommandArgs[$i] -ne "--") {
        switch ($CommandArgs[$i]) {
            "--name" {
                $i++
                if ($i -ge $CommandArgs.Count) { Die "missing service name after --name" }
                if ($name -and $name -ne $CommandArgs[$i]) { Die "service name specified more than once: $name and $($CommandArgs[$i])" }
                $name = $CommandArgs[$i]
                $i++
            }
            "--port" {
                $i++
                if ($i -ge $CommandArgs.Count) { Die "missing port after --port" }
                if ($CommandArgs[$i] -eq "auto") {
                    $port = ""
                    $autoPort = $true
                } else {
                    Validate-Port $CommandArgs[$i]
                    if ($port -and $port -ne $CommandArgs[$i]) { Die "port specified more than once: $port and $($CommandArgs[$i])" }
                    $port = $CommandArgs[$i]
                    $autoPort = $false
                }
                $i++
            }
            "--env" {
                $i++
                if ($i -ge $CommandArgs.Count) { Die "missing environment name after --env" }
                $envMode = "env"
                $envName = $CommandArgs[$i]
                $i++
            }
            "--no-env" {
                $envMode = "none"
                $i++
            }
            "--ask-env" {
                $envMode = "ask"
                $i++
            }
            default {
                Show-PortStartUsage
                Die "unknown option before '--': $($CommandArgs[$i])"
            }
        }
    }

    if ($i -ge $CommandArgs.Count -or $CommandArgs[$i] -ne "--") {
        Show-PortStartUsage
        Die "missing required '--' before command"
    }
    $i++
    if ($i -ge $CommandArgs.Count) {
        Show-PortStartUsage
        Die "missing command to run"
    }
    $command = @($CommandArgs[$i..($CommandArgs.Count - 1)])

    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = Read-Host "Service name"
    }
    Validate-Name $name

    With-PortLock {
        $entries = Read-Registry
        if (Find-ByName $entries $name) { Die "named port service already exists: $name" }

        if ($autoPort) {
            $selectedPort = Find-AvailablePort 8000 $entries
        } else {
            Validate-Port $port
            $selectedPort = [int]$port
            if (Find-ByPort $entries $selectedPort) { Die "port is already managed by cli-tools: $selectedPort" }
            if (!(Is-PortFree $selectedPort)) { Die "port is already listening: $selectedPort" }
        }

        for ($j = 0; $j -lt $command.Count; $j++) {
            $command[$j] = $command[$j].Replace("{PORT}", [string]$selectedPort)
        }

        if ($envMode -eq "env") {
            $command = @("conda", "run", "--no-capture-output", "-n", $envName) + $command
        } elseif ($envMode -eq "ask") {
            Warn "--ask-env is not implemented in Windows native mode; running command as-is"
        }

        Validate-Command $command
        $entry = Start-ServiceEntry $name $selectedPort $command (Get-Location).ProviderPath
        $entries += $entry
        Write-RegistryRaw $entries

        Write-Host "Started named port service: $name"
        Write-Host "  port: $selectedPort"
        if ($envMode -eq "env") { Write-Host "  environment: $envName" }
        Write-Host "  pid: $($entry.Pid)"
        Write-Host "  log: $($entry.LogPath)"
        Write-Host "  status: $($entry.Status)"
    }
}

function Cmd-PortList([string[]]$CommandArgs) {
    $full = $false
    foreach ($arg in $CommandArgs) {
        if ($arg -eq "-h" -or $arg -eq "--help") {
@"
Usage:
  cli-tools port-list [--full]

List named port services managed by Windows-native cli-tools.
"@ | Write-Host
            return
        } elseif ($arg -eq "--full") {
            $full = $true
        } elseif ($arg -eq "--remote") {
            Die "--remote is not implemented in Windows native mode"
        } else {
            Die "unknown argument: $arg"
        }
    }

    With-PortLock {
        $entries = Read-Registry | Sort-Object Name, Port
        if ($entries.Count -eq 0) {
            Write-Host "No named port services."
            return
        }
        if ($full) {
            "{0,-20} {1,-6} {2,-9} {3,-8} {4,-20} {5}" -f "NAME", "PORT", "STATUS", "PID", "STARTED", "LOG" | Write-Host
            foreach ($e in $entries) {
                $status = "running"
                if (Is-PortListening ([int]$e.Port)) { $status = "listening" }
                "{0,-20} {1,-6} {2,-9} {3,-8} {4,-20} {5}" -f $e.Name, $e.Port, $status, $e.Pid, $e.StartTime, $e.LogPath | Write-Host
                Write-Host "  command: $($e.CommandText)"
                Write-Host "  cwd: $($e.Cwd)"
            }
        } else {
            "{0,-20} {1,-6} {2,-9} {3}" -f "NAME", "PORT", "STATUS", "STARTED" | Write-Host
            foreach ($e in $entries) {
                $status = "running"
                if (Is-PortListening ([int]$e.Port)) { $status = "listening" }
                "{0,-20} {1,-6} {2,-9} {3}" -f $e.Name, $e.Port, $status, $e.StartTime | Write-Host
            }
        }
    }
}

function Cmd-PortStop([string[]]$CommandArgs) {
    if ($CommandArgs.Count -gt 0 -and ($CommandArgs[0] -eq "-h" -or $CommandArgs[0] -eq "--help")) {
@"
Usage:
  cli-tools port-stop <name-or-port> [...]
  cli-tools port-stop --all
"@ | Write-Host
        return
    }
    if ($CommandArgs.Count -eq 0) { Die "interactive mode is not implemented; pass <name-or-port> or --all" }
    With-PortLock {
        $entries = Read-Registry
        if ($entries.Count -eq 0) {
            Write-Host "No named port services."
            return
        }
        if ($CommandArgs.Count -eq 1 -and $CommandArgs[0] -eq "--all") {
            foreach ($e in $entries) { Stop-ServiceEntry $e }
            Write-RegistryRaw @()
            Write-Host "Stopped all named port services."
            return
        }
        if ($CommandArgs -contains "--all") { Die "--all cannot be combined with service names or ports" }
        $targets = @()
        foreach ($target in $CommandArgs) {
            $entry = Entry-ForTarget $entries $target
            if (!($targets | Where-Object { $_.Name -eq $entry.Name })) { $targets += $entry }
        }
        foreach ($entry in $targets) { Stop-ServiceEntry $entry }
        $remaining = @($entries | Where-Object {
            $name = $_.Name
            -not ($targets | Where-Object { $_.Name -eq $name })
        })
        Write-RegistryRaw $remaining
    }
}

function Cmd-PortRename([string[]]$CommandArgs) {
    if ($CommandArgs.Count -gt 0 -and ($CommandArgs[0] -eq "-h" -or $CommandArgs[0] -eq "--help")) {
@"
Usage:
  cli-tools port-rename <name-or-port> <new-name>
"@ | Write-Host
        return
    }
    if ($CommandArgs.Count -ne 2) { Die "expected <name-or-port> and <new-name>" }
    $target = $CommandArgs[0]
    $newName = $CommandArgs[1]
    Validate-Name $newName
    With-PortLock {
        $entries = Read-Registry
        $entry = Entry-ForTarget $entries $target
        if (Find-ByName $entries $newName) { Die "named port service already exists: $newName" }
        $oldName = $entry.Name
        $entry.Name = $newName
        Write-RegistryRaw $entries
        Write-Host "Renamed named port service: $oldName -> $newName"
        Write-Host "  port: $($entry.Port)"
        Write-Host "  pid: $($entry.Pid)"
        Write-Host "  log: $($entry.LogPath)"
    }
}

function Cmd-PortRestart([string[]]$CommandArgs) {
    if ($CommandArgs.Count -gt 0 -and ($CommandArgs[0] -eq "-h" -or $CommandArgs[0] -eq "--help")) {
@"
Usage:
  cli-tools port-restart <name-or-port> [...]
"@ | Write-Host
        return
    }
    if ($CommandArgs.Count -eq 0) { Die "interactive mode is not implemented; pass <name-or-port>" }
    With-PortLock {
        $entries = Read-Registry
        $targets = @()
        foreach ($target in $CommandArgs) {
            $entry = Entry-ForTarget $entries $target
            if (!($targets | Where-Object { $_.Name -eq $entry.Name })) { $targets += $entry }
        }
        $newEntries = @($entries | Where-Object {
            $name = $_.Name
            -not ($targets | Where-Object { $_.Name -eq $name })
        })
        foreach ($entry in $targets) {
            Stop-ServiceEntry $entry
            $command = @($entry.Command)
            $newEntry = Start-ServiceEntry $entry.Name ([int]$entry.Port) $command $entry.Cwd
            $newEntries += $newEntry
            Write-Host "Restarted named port service: $($entry.Name)"
            Write-Host "  port: $($entry.Port)"
            Write-Host "  pid: $($newEntry.Pid)"
            Write-Host "  log: $($newEntry.LogPath)"
            Write-Host "  status: $($newEntry.Status)"
        }
        Write-RegistryRaw $newEntries
    }
}

function Cmd-PortClearCache([string[]]$CommandArgs) {
    if ($CommandArgs.Count -gt 0 -and ($CommandArgs[0] -eq "-h" -or $CommandArgs[0] -eq "--help")) {
@"
Usage:
  cli-tools port-clear-cache
"@ | Write-Host
        return
    }
    if ($CommandArgs.Count -ne 0) { Die "this command does not accept arguments" }
    With-PortLock {
        $entries = Read-Registry
        if ($entries.Count -ne 0) {
            Cmd-PortList @()
            Die "stop active services before clearing the port cache"
        }
        $cleared = $false
        if (Test-Path -LiteralPath $Script:RegistryPath) {
            Remove-Item -LiteralPath $Script:RegistryPath -Force
            $cleared = $true
        }
        foreach ($dir in @($Script:LogDir, $Script:RunDir)) {
            if (Test-Path -LiteralPath $dir) {
                Remove-Item -LiteralPath $dir -Recurse -Force
                $cleared = $true
            }
        }
        if ($cleared) {
            Write-Host "Cleared port cache: $Script:PortCacheDir"
        } else {
            Write-Host "Port cache is already clear: $Script:PortCacheDir"
        }
    }
}

if ($CliArgs.Count -eq 0) {
    Cmd-List @()
    exit 0
}

$commandName = $CliArgs[0]
$rest = @()
if ($CliArgs.Count -gt 1) { $rest = @($CliArgs[1..($CliArgs.Count - 1)]) }

switch ($commandName) {
    "-h" { Show-MainUsage }
    "--help" { Show-MainUsage }
    "help" { Show-MainUsage }
    "list" { Cmd-List $rest }
    "port-start" { Cmd-PortStart $rest }
    "port-list" { Cmd-PortList $rest }
    "port-stop" { Cmd-PortStop $rest }
    "port-restart" { Cmd-PortRestart $rest }
    "port-rename" { Cmd-PortRename $rest }
    "port-clear-cache" { Cmd-PortClearCache $rest }
    default {
        Die "unknown or not yet implemented Windows-native cli-tools command: $commandName; run 'cli-tools list'"
    }
}


