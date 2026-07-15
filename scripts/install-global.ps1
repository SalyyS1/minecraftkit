[CmdletBinding()]
param(
    [string]$SourceRoot,
    [string]$CodexSkillsRoot = (Join-Path $HOME '.agents\skills'),
    [string]$ClaudeSkillsRoot = (Join-Path $HOME '.claude\skills'),
    [string]$ClaudeCommandsRoot = (Join-Path $HOME '.claude\commands'),
    [string]$Python = 'python',
    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Split-Path -Parent $PSScriptRoot
}
$CanonicalSkillName = 'minecraftkit'
$LegacySkillName = 'minecraft-rpg-kit'
$ExcludedNames = @('dist', '__pycache__', '.git', '.gitignore', '.gitattributes')

function Get-FullPath {
    param([Parameter(Mandatory)][string]$Path)
    return [IO.Path]::GetFullPath($Path)
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Path
    )
    $rootPath = (Get-FullPath $Root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $rootUri = [Uri]::new($rootPath)
    $pathUri = [Uri]::new((Get-FullPath $Path))
    return [Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString()).Replace('/', [IO.Path]::DirectorySeparatorChar)
}

function Test-ReparsePoint {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force
    return [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Test-PathsOverlap {
    param(
        [Parameter(Mandatory)][string]$First,
        [Parameter(Mandatory)][string]$Second
    )
    $firstPath = (Get-FullPath $First).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $secondPath = (Get-FullPath $Second).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    if ($firstPath.Equals($secondPath, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    $firstPrefix = $firstPath + [IO.Path]::DirectorySeparatorChar
    $secondPrefix = $secondPath + [IO.Path]::DirectorySeparatorChar
    return $firstPrefix.StartsWith($secondPrefix, [StringComparison]::OrdinalIgnoreCase) -or
        $secondPrefix.StartsWith($firstPrefix, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-NoReparseAncestors {
    param([Parameter(Mandatory)][string]$Path)
    $current = Get-FullPath $Path
    while ($current) {
        if ((Test-Path -LiteralPath $current) -and (Test-ReparsePoint $current)) {
            throw "Reparse-point path or ancestor is not allowed: $current"
        }
        $parent = [IO.Directory]::GetParent($current)
        if ($null -eq $parent -or $parent.FullName.Equals($current, [StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $current = $parent.FullName
    }
}

function Assert-DirectChild {
    param(
        [Parameter(Mandatory)][string]$Child,
        [Parameter(Mandatory)][string]$Parent
    )
    $fullChild = Get-FullPath $Child
    $fullParent = (Get-FullPath $Parent).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $childParent = [IO.Path]::GetDirectoryName($fullChild).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not $childParent.Equals($fullParent, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe path is not a direct child of $fullParent`: $fullChild"
    }
}

function Assert-SafeName {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Label
    )
    if ($Name -cnotmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
        throw "Unsafe $Label name: $Name"
    }
}

function Assert-PhysicalTree {
    param([Parameter(Mandatory)][string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Payload directory does not exist: $Root"
    }
    if (Test-ReparsePoint $Root) { throw "Reparse-point root is not allowed: $Root" }
    foreach ($item in Get-ChildItem -LiteralPath $Root -Recurse -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Reparse point is not allowed in payload: $($item.FullName)"
        }
    }
}

function Get-PayloadFiles {
    param([Parameter(Mandatory)][string]$Root)
    $fullRoot = Get-FullPath $Root
    return @(
        Get-ChildItem -LiteralPath $fullRoot -Recurse -File -Force |
            Where-Object {
                $relative = Get-RelativePath -Root $fullRoot -Path $_.FullName
                $parts = $relative -split '[\\/]'
                -not ($parts | Where-Object { $ExcludedNames -contains $_ }) -and
                $_.Extension -ne '.pyc' -and
                -not ($parts | Where-Object {
                    $_ -like '.api-stage-*' -or $_ -like '.web-stage-*' -or
                    $_ -like '.minecraftkit-stage-*' -or $_ -like '.minecraftkit-commands-stage-*'
                })
            } |
            Sort-Object FullName
    )
}

function Copy-Payload {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination
    )
    $sourcePath = Get-FullPath $Source
    $files = @(Get-PayloadFiles $sourcePath)
    if (-not $files.Count) { throw "Payload has no files: $sourcePath" }
    foreach ($file in $files) {
        $relative = Get-RelativePath -Root $sourcePath -Path $file.FullName
        $candidate = Join-Path $Destination $relative
        if ((Get-FullPath $candidate).Length -ge 240) {
            throw "Destination path exceeds conservative Windows limit; choose a shorter install root: $candidate"
        }
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($file in $files) {
        $relative = Get-RelativePath -Root $sourcePath -Path $file.FullName
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

function Get-ContentManifest {
    param([Parameter(Mandatory)][string]$Root)
    $fullRoot = Get-FullPath $Root
    return @(
        foreach ($file in @(Get-PayloadFiles $fullRoot)) {
            $relative = (Get-RelativePath -Root $fullRoot -Path $file.FullName).Replace('\', '/')
            $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$relative|$($file.Length)|$hash"
        }
    )
}

function Assert-ManifestMatch {
    param(
        [Parameter(Mandatory)][string[]]$Expected,
        [Parameter(Mandatory)][string[]]$Actual,
        [Parameter(Mandatory)][string]$Label
    )
    if (($Expected -join "`n") -cne ($Actual -join "`n")) {
        throw "Payload hash mismatch: $Label"
    }
}

function Remove-SafeTree {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Parent
    )
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Assert-DirectChild -Child $Path -Parent $Parent
    if (Test-ReparsePoint $Path) { throw "Refusing to delete reparse point: $Path" }
    if (Test-Path -LiteralPath $Path -PathType Container) { Assert-PhysicalTree $Path }
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Get-DomainDefinitions {
    param([Parameter(Mandatory)][string]$Root)
    $catalogPath = Join-Path $Root 'data\minecraft-domain-catalog.json'
    if (-not (Test-Path -LiteralPath $catalogPath -PathType Leaf)) {
        throw "Minecraft domain catalog is missing: $catalogPath"
    }
    $catalog = Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $domains = @($catalog.domains)
    if ($catalog.schema_version -ne 1 -or $domains.Count -ne 9) {
        throw 'Minecraft domain catalog must contain exactly nine schema-v1 domains.'
    }
    $definitions = @()
    $seenIds = @{}
    $seenDirectories = @{}
    foreach ($domain in $domains) {
        $id = [string]$domain.id
        $directory = [string]$domain.skill_directory
        $route = [string]$domain.route
        Assert-SafeName -Name $id -Label 'domain'
        Assert-SafeName -Name $directory -Label 'skill directory'
        if ($route -cne "mc:$id" -or $directory -cne "mc-$id") {
            throw "Domain route/directory mismatch for $id"
        }
        if ($seenIds.ContainsKey($id) -or $seenDirectories.ContainsKey($directory)) {
            throw "Duplicate Minecraft domain install name: $id / $directory"
        }
        $seenIds[$id] = $true
        $seenDirectories[$directory] = $true
        $definitions += [pscustomobject]@{ Id = $id; Directory = $directory; Route = $route }
    }
    return @($definitions | Sort-Object Id)
}

function New-InstallRecord {
    param(
        [Parameter(Mandatory)][string]$Client,
        [Parameter(Mandatory)][string]$Kind,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Container,
        [Parameter(Mandatory)][string]$Stamp,
        [Parameter(Mandatory)][string]$Transaction
    )
    Assert-SafeName -Name $Name -Label 'target'
    $target = Join-Path $Root $Name
    $stage = Join-Path $Container $Name
    $backup = Join-Path $Root "$Name.backup-$Stamp-$Transaction"
    Assert-DirectChild -Child $target -Parent $Root
    Assert-DirectChild -Child $stage -Parent $Container
    Assert-DirectChild -Child $backup -Parent $Root
    return [pscustomobject]@{
        Client = $Client
        Kind = $Kind
        Name = $Name
        Source = (Get-FullPath $Source)
        Root = (Get-FullPath $Root)
        Container = (Get-FullPath $Container)
        Stage = (Get-FullPath $stage)
        Target = (Get-FullPath $target)
        Backup = (Get-FullPath $backup)
        ExpectedManifest = @()
        HadTarget = $false
        Promoted = $false
    }
}

$source = Get-FullPath $SourceRoot
if (-not (Test-Path -LiteralPath (Join-Path $source 'SKILL.md') -PathType Leaf)) {
    throw "Invalid MinecraftKit source: $source"
}
Assert-NoReparseAncestors $source
Assert-PhysicalTree $source

$codexRoot = Get-FullPath $CodexSkillsRoot
$claudeRoot = Get-FullPath $ClaudeSkillsRoot
$commandsRoot = Get-FullPath $ClaudeCommandsRoot
$destinationRoots = @($codexRoot, $claudeRoot, $commandsRoot)
for ($first = 0; $first -lt $destinationRoots.Count; $first++) {
    if (Test-PathsOverlap -First $source -Second $destinationRoots[$first]) {
        throw "The canonical source and destination roots must be disjoint: $source; $($destinationRoots[$first])"
    }
    Assert-NoReparseAncestors $destinationRoots[$first]
    for ($second = $first + 1; $second -lt $destinationRoots.Count; $second++) {
        if (Test-PathsOverlap -First $destinationRoots[$first] -Second $destinationRoots[$second]) {
            throw "Install roots must be disjoint physical directories: $($destinationRoots[$first]); $($destinationRoots[$second])"
        }
    }
}

$domains = @(Get-DomainDefinitions -Root $source)
$wrappersSource = Join-Path $source 'skill-wrappers'
$commandsSource = Join-Path $source 'commands\mc'
Assert-PhysicalTree $wrappersSource
Assert-PhysicalTree $commandsSource
foreach ($domain in $domains) {
    $wrapper = Join-Path $wrappersSource $domain.Directory
    $command = Join-Path $commandsSource "$($domain.Id).md"
    Assert-DirectChild -Child $wrapper -Parent $wrappersSource
    Assert-DirectChild -Child $command -Parent $commandsSource
    if (-not (Test-Path -LiteralPath (Join-Path $wrapper 'SKILL.md') -PathType Leaf)) {
        throw "Skill wrapper is missing SKILL.md: $wrapper"
    }
    if (-not (Test-Path -LiteralPath $command -PathType Leaf)) {
        throw "Claude command is missing: $command"
    }
}

$transaction = [guid]::NewGuid().ToString('N')
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$codexContainer = Join-Path $codexRoot ".minecraftkit-stage-$transaction"
$claudeContainer = Join-Path $claudeRoot ".minecraftkit-stage-$transaction"
$commandsContainer = Join-Path $commandsRoot ".minecraftkit-commands-stage-$transaction"
Assert-DirectChild -Child $codexContainer -Parent $codexRoot
Assert-DirectChild -Child $claudeContainer -Parent $claudeRoot
Assert-DirectChild -Child $commandsContainer -Parent $commandsRoot

$records = @(
    New-InstallRecord -Client 'Codex' -Kind 'canonical' -Name $CanonicalSkillName -Source $source -Root $codexRoot -Container $codexContainer -Stamp $stamp -Transaction $transaction
    New-InstallRecord -Client 'Claude' -Kind 'canonical' -Name $CanonicalSkillName -Source $source -Root $claudeRoot -Container $claudeContainer -Stamp $stamp -Transaction $transaction
)
foreach ($domain in $domains) {
    $wrapperSource = Join-Path $wrappersSource $domain.Directory
    $records += New-InstallRecord -Client 'Codex' -Kind 'wrapper' -Name $domain.Directory -Source $wrapperSource -Root $codexRoot -Container $codexContainer -Stamp $stamp -Transaction $transaction
    $records += New-InstallRecord -Client 'Claude' -Kind 'wrapper' -Name $domain.Directory -Source $wrapperSource -Root $claudeRoot -Container $claudeContainer -Stamp $stamp -Transaction $transaction
}
$records += New-InstallRecord -Client 'Claude' -Kind 'commands' -Name 'mc' -Source $commandsSource -Root $commandsRoot -Container $commandsContainer -Stamp $stamp -Transaction $transaction

if ($PlanOnly) {
    $installs = @(
        foreach ($record in $records) {
            [ordered]@{
                client = $record.Client
                kind = $record.Kind
                name = $record.Name
                source = $record.Source
                target = $record.Target
                backup = $record.Backup
            }
        }
    )
    [ordered]@{
        schemaVersion = 1
        canonicalSkill = $CanonicalSkillName
        installs = $installs
        preservedLegacyTargets = @(
            (Join-Path $codexRoot $LegacySkillName),
            (Join-Path $claudeRoot $LegacySkillName)
        )
    } | ConvertTo-Json -Depth 5
    return
}

foreach ($root in $destinationRoots) {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Assert-NoReparseAncestors $root
}
$containers = @($codexContainer, $claudeContainer, $commandsContainer)
foreach ($container in $containers) {
    if (Test-Path -LiteralPath $container) {
        throw "Transaction staging path already exists: $container"
    }
}

try {
    foreach ($record in $records) {
        $record.ExpectedManifest = @(Get-ContentManifest -Root $record.Source)
        Copy-Payload -Source $record.Source -Destination $record.Stage
        Assert-PhysicalTree $record.Stage
        Assert-ManifestMatch -Expected $record.ExpectedManifest -Actual @(Get-ContentManifest -Root $record.Stage) -Label "$($record.Client) $($record.Name) stage"
        if ($record.Kind -eq 'canonical') {
            & $Python -B (Join-Path $record.Stage 'scripts\validate_kit.py') $record.Stage | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "$($record.Client) staged canonical validation failed." }
        }
    }

    foreach ($record in $records) {
        if (Test-Path -LiteralPath $record.Backup) {
            throw "Refusing to overwrite an existing backup: $($record.Backup)"
        }
        if (Test-Path -LiteralPath $record.Target) {
            if (Test-ReparsePoint $record.Target) { throw "Existing target is a reparse point: $($record.Target)" }
            if (Test-Path -LiteralPath $record.Target -PathType Container) { Assert-PhysicalTree $record.Target }
            $record.HadTarget = $true
            Move-Item -LiteralPath $record.Target -Destination $record.Backup
            if ((Test-Path -LiteralPath $record.Target) -or -not (Test-Path -LiteralPath $record.Backup)) {
                throw "Target backup did not complete: $($record.Target)"
            }
        }
    }

    foreach ($record in $records) {
        if (Test-Path -LiteralPath $record.Target) {
            throw "Target appeared during transaction: $($record.Target)"
        }
        $record.Promoted = $true
        Move-Item -LiteralPath $record.Stage -Destination $record.Target
        if (-not (Test-Path -LiteralPath $record.Target -PathType Container)) {
            throw "Payload promotion did not complete: $($record.Target)"
        }
        Assert-PhysicalTree $record.Target
        Assert-ManifestMatch -Expected $record.ExpectedManifest -Actual @(Get-ContentManifest -Root $record.Target) -Label "$($record.Client) $($record.Name) install"
        if ($record.Kind -eq 'canonical') {
            & $Python -B (Join-Path $record.Target 'scripts\query_api.py') ActiveModel --plugin ModelEngine --limit 1 | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "$($record.Client) canonical smoke test failed." }
        }
    }
}
catch {
    $installError = $_
    $rollbackErrors = @()
    for ($recordIndex = $records.Count - 1; $recordIndex -ge 0; $recordIndex--) {
        $record = $records[$recordIndex]
        try {
            if ($record.Promoted -and (Test-Path -LiteralPath $record.Target)) {
                Remove-SafeTree -Path $record.Target -Parent $record.Root
            }
        }
        catch {
            $rollbackErrors += "$($record.Client) $($record.Name) cleanup failed: $($_.Exception.Message)"
        }
        try {
            if ($record.HadTarget -and (Test-Path -LiteralPath $record.Backup)) {
                if (Test-Path -LiteralPath $record.Target) {
                    throw "Cannot restore backup because target exists: $($record.Target)"
                }
                Move-Item -LiteralPath $record.Backup -Destination $record.Target
            }
        }
        catch {
            $rollbackErrors += "$($record.Client) $($record.Name) restore failed: $($_.Exception.Message)"
        }
    }
    if ($rollbackErrors.Count) {
        $details = $rollbackErrors -join '; '
        throw [InvalidOperationException]::new("Installation failed: $($installError.Exception.Message). Rollback errors: $details", $installError.Exception)
    }
    $PSCmdlet.ThrowTerminatingError($installError)
}
finally {
    for ($index = $containers.Count - 1; $index -ge 0; $index--) {
        $container = $containers[$index]
        if (Test-Path -LiteralPath $container) {
            Remove-SafeTree -Path $container -Parent (Split-Path -Parent $container)
        }
    }
}

foreach ($record in $records) {
    $backupText = if ($record.HadTarget) { "; backup=$($record.Backup)" } else { '' }
    Write-Output "$($record.Client) $($record.Kind): installed physical copy at $($record.Target)$backupText"
}
Write-Output "Legacy targets preserved: $(Join-Path $codexRoot $LegacySkillName); $(Join-Path $claudeRoot $LegacySkillName)"
