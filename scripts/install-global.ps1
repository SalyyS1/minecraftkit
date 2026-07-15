[CmdletBinding()]
param(
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$CodexSkillsRoot = (Join-Path $HOME '.agents\skills'),
    [string]$ClaudeSkillsRoot = (Join-Path $HOME '.claude\skills'),
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$SkillName = 'minecraft-rpg-kit'
$ExcludedDirectories = @('dist', '__pycache__', '.git', '.gitignore', '.gitattributes')

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

function Assert-PhysicalTree {
    param([Parameter(Mandatory)][string]$Root)
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
                -not ($parts | Where-Object { $ExcludedDirectories -contains $_ }) -and
                $_.Extension -ne '.pyc' -and
                -not ($parts | Where-Object { $_ -like '.api-stage-*' -or $_ -like '.web-stage-*' })
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
    foreach ($file in $files) {
        $relative = Get-RelativePath -Root $sourcePath -Path $file.FullName
        $candidate = Join-Path $Destination $relative
        if ((Get-FullPath $candidate).Length -ge 240) {
            throw "Destination path exceeds conservative Windows limit; choose a shorter skill root: $candidate"
        }
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($file in $files) {
        $relative = Get-RelativePath -Root $sourcePath -Path $file.FullName
        $target = Join-Path $Destination $relative
        $targetParent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

function Get-ContentManifest {
    param(
        [Parameter(Mandatory)][string]$Root,
        [switch]$ApplySourceFilter
    )
    $fullRoot = Get-FullPath $Root
    $files = if ($ApplySourceFilter) { Get-PayloadFiles $fullRoot } else { @(Get-ChildItem -LiteralPath $fullRoot -Recurse -File -Force | Sort-Object FullName) }
    return @(
        foreach ($file in $files) {
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
    $expectedText = $Expected -join "`n"
    $actualText = $Actual -join "`n"
    if ($expectedText -cne $actualText) { throw "Payload hash mismatch: $Label" }
}

function Remove-SafeTree {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Parent
    )
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Assert-DirectChild -Child $Path -Parent $Parent
    if (Test-ReparsePoint $Path) { throw "Refusing to delete reparse point: $Path" }
    Remove-Item -LiteralPath $Path -Recurse -Force
}

$source = Get-FullPath $SourceRoot
if (-not (Test-Path -LiteralPath (Join-Path $source 'SKILL.md') -PathType Leaf)) {
    throw "Invalid MinecraftRPG Kit source: $source"
}
Assert-NoReparseAncestors $source
Assert-PhysicalTree $source

$roots = @((Get-FullPath $CodexSkillsRoot), (Get-FullPath $ClaudeSkillsRoot))
if (Test-PathsOverlap -First $roots[0] -Second $roots[1]) {
    throw 'Codex and Claude skill roots must be disjoint physical directories.'
}
foreach ($root in $roots) {
    if (Test-PathsOverlap -First $source -Second $root) {
        throw "The canonical source and skill roots must be disjoint: $source; $root"
    }
}
foreach ($root in $roots) {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Assert-NoReparseAncestors $root
}

$sourceManifest = @(Get-ContentManifest -Root $source -ApplySourceFilter)
$transaction = [guid]::NewGuid().ToString('N')
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$records = @()

try {
    for ($index = 0; $index -lt $roots.Count; $index++) {
        $client = if ($index -eq 0) { 'Codex' } else { 'Claude' }
        $root = $roots[$index]
        $container = Join-Path $root ".minecraft-rpg-kit-stage-$transaction"
        $stage = Join-Path $container $SkillName
        $target = Join-Path $root $SkillName
        $backup = Join-Path $root "$SkillName.backup-$stamp-$transaction"
        Assert-DirectChild -Child $container -Parent $root
        Assert-DirectChild -Child $target -Parent $root
        Assert-DirectChild -Child $backup -Parent $root
        $record = [pscustomobject]@{
            Client = $client; Root = $root; Container = $container; Stage = $stage;
            Target = $target; Backup = $backup; HadTarget = $false; Promoted = $false
        }
        $records += $record
        if (Test-Path -LiteralPath $container) { Remove-SafeTree -Path $container -Parent $root }
        Copy-Payload -Source $source -Destination $stage
        Assert-PhysicalTree $stage
        & $Python -B (Join-Path $stage 'scripts\validate_kit.py') $stage
        if ($LASTEXITCODE -ne 0) { throw "$client staged validation failed." }
        $stageManifest = @(Get-ContentManifest -Root $stage)
        Assert-ManifestMatch -Expected $sourceManifest -Actual $stageManifest -Label "$client stage"
    }

    foreach ($record in $records) {
        if (Test-Path -LiteralPath $record.Target) {
            if (Test-ReparsePoint $record.Target) { throw "Existing target is a reparse point: $($record.Target)" }
            Move-Item -LiteralPath $record.Target -Destination $record.Backup
            $record.HadTarget = $true
        }
    }
    foreach ($record in $records) {
        Move-Item -LiteralPath $record.Stage -Destination $record.Target
        $record.Promoted = $true
        Assert-PhysicalTree $record.Target
        $installedManifest = @(Get-ContentManifest -Root $record.Target)
        Assert-ManifestMatch -Expected $sourceManifest -Actual $installedManifest -Label "$($record.Client) install"
        & $Python -B (Join-Path $record.Target 'scripts\query_api.py') ActiveModel --plugin ModelEngine --limit 1 | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "$($record.Client) API smoke test failed." }
    }
}
catch {
    $installError = $_
    $rollbackErrors = @()
    foreach ($record in $records) {
        try {
            if ($record.Promoted -and (Test-Path -LiteralPath $record.Target)) {
                Remove-SafeTree -Path $record.Target -Parent $record.Root
            }
        }
        catch {
            $rollbackErrors += "$($record.Client) target cleanup failed: $($_.Exception.Message)"
        }
        try {
            if ($record.HadTarget -and (Test-Path -LiteralPath $record.Backup)) {
                Move-Item -LiteralPath $record.Backup -Destination $record.Target
            }
        }
        catch {
            $rollbackErrors += "$($record.Client) backup restore failed: $($_.Exception.Message)"
        }
    }
    if ($rollbackErrors.Count) {
        $details = $rollbackErrors -join '; '
        throw [InvalidOperationException]::new("Installation failed: $($installError.Exception.Message). Rollback errors: $details", $installError.Exception)
    }
    $PSCmdlet.ThrowTerminatingError($installError)
}
finally {
    foreach ($record in $records) {
        if (Test-Path -LiteralPath $record.Container) {
            Remove-SafeTree -Path $record.Container -Parent $record.Root
        }
    }
}

foreach ($record in $records) {
    $backupText = if ($record.HadTarget) { "; backup=$($record.Backup)" } else { '' }
    Write-Output "$($record.Client): installed physical copy at $($record.Target)$backupText"
}
