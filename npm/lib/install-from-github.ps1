[CmdletBinding()]
param(
    [ValidateSet('codex', 'claude', 'both')]
    [string]$Target = 'both',
    [ValidatePattern('^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')]
    [string]$Repository = 'SalyyS1/minecraftkit',
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+$')]
    [string]$Version,
    [string]$CodexSkillsRoot = (Join-Path $HOME '.agents\skills'),
    [string]$ClaudeSkillsRoot = (Join-Path $HOME '.claude\skills'),
    [string]$ClaudeCommandsRoot = (Join-Path $HOME '.claude\commands'),
    [string]$Python = 'python',
    [switch]$PlanOnly,
    [switch]$AllowTestSource,
    [string]$TestReleaseDirectory
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$MaximumArchiveBytes = 64MB
$MaximumChecksumBytes = 64KB
$MaximumArchiveEntries = 20000
$MaximumExpandedBytes = 512MB
$MaximumRedirects = 5
$AssetDownloadHosts = @(
    'github.com',
    'objects.githubusercontent.com',
    'release-assets.githubusercontent.com'
)

function Get-FullPath {
    param([Parameter(Mandatory)][string]$Path)
    return [IO.Path]::GetFullPath($Path)
}

function Test-ReparsePoint {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force
    return [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
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
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Directory does not exist: $Root"
    }
    if (Test-ReparsePoint $Root) { throw "Reparse-point root is not allowed: $Root" }
    foreach ($item in Get-ChildItem -LiteralPath $Root -Recurse -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Reparse point is not allowed: $($item.FullName)"
        }
    }
}

function Assert-GitHubHttpsUri {
    param(
        [Parameter(Mandatory)][string]$Value,
        [Parameter(Mandatory)][string[]]$Hosts,
        [Parameter(Mandatory)][string]$Label
    )
    $uri = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri)) {
        throw "$Label is not an absolute URI."
    }
    if ($uri.Scheme -cne 'https' -or -not $uri.IsDefaultPort -or $uri.UserInfo -or $uri.Fragment) {
        throw "$Label must use default-port HTTPS without credentials or a fragment: $Value"
    }
    if ($Hosts -cnotcontains $uri.DnsSafeHost.ToLowerInvariant()) {
        throw "$Label host is not allowed: $($uri.DnsSafeHost)"
    }
    return $uri
}

function Get-GitHubHeaders {
    $headers = @{
        Accept = 'application/vnd.github+json'
        'User-Agent' = 'minecraftkit-secure-bootstrap/2.1'
        'X-GitHub-Api-Version' = '2022-11-28'
    }
    $token = if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
        $env:GITHUB_TOKEN
    }
    elseif (-not [string]::IsNullOrWhiteSpace($env:GH_TOKEN)) {
        $env:GH_TOKEN
    }
    else {
        $null
    }
    if ($token) {
        if ($token.IndexOfAny(@([char]13, [char]10)) -ge 0) {
            throw 'GitHub token contains invalid header characters.'
        }
        $headers.Authorization = "Bearer $token"
    }
    return $headers
}

function Get-PublicAssetHeaders {
    param([Parameter(Mandatory)][hashtable]$ApiHeaders)
    $userAgent = [string]$ApiHeaders['User-Agent']
    if ([string]::IsNullOrWhiteSpace($userAgent)) {
        throw 'Public asset requests require a nonempty User-Agent.'
    }
    return @{
        Accept = 'application/octet-stream'
        'User-Agent' = $userAgent
    }
}

function Get-BoundedAssetSize {
    param(
        [Parameter(Mandatory)]$Asset,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][long]$MaximumBytes
    )
    if (@($Asset.PSObject.Properties.Name) -cnotcontains 'size') {
        throw "Release asset metadata is missing size for $Name."
    }
    $size = [long]0
    if (-not [long]::TryParse(
        [string]$Asset.size,
        [Globalization.NumberStyles]::None,
        [Globalization.CultureInfo]::InvariantCulture,
        [ref]$size
    ) -or $size -le 0) {
        throw "Release asset metadata has an invalid size for $Name."
    }
    if ($size -gt $MaximumBytes) {
        throw "Release asset metadata exceeds the $MaximumBytes byte limit for $Name."
    }
    return $size
}

function Read-ReleaseMetadata {
    param(
        [Parameter(Mandatory)][Uri]$ApiUri,
        [Parameter(Mandatory)][hashtable]$Headers,
        [string]$FixtureRoot
    )
    if ($FixtureRoot) {
        $metadataPath = Join-Path $FixtureRoot 'release.json'
        Assert-DirectChild -Child $metadataPath -Parent $FixtureRoot
        if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf) -or (Test-ReparsePoint $metadataPath)) {
            throw "Safe fixture release metadata is missing: $metadataPath"
        }
        return [IO.File]::ReadAllText($metadataPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
    }
    return Invoke-RestMethod -Uri $ApiUri.AbsoluteUri -Headers $Headers -Method Get
}

function Select-ReleaseAssets {
    param(
        [Parameter(Mandatory)]$Release,
        [string]$RequestedVersion
    )
    if (-not $RequestedVersion) {
        $properties = @($Release.PSObject.Properties.Name)
        if ($properties -cnotcontains 'draft' -or $properties -cnotcontains 'prerelease') {
            throw 'Latest release metadata must declare draft and prerelease state.'
        }
        if ([bool]$Release.draft -or [bool]$Release.prerelease) {
            throw 'Latest installation refuses draft or prerelease releases; request a named version explicitly.'
        }
    }

    $assets = @($Release.assets | Where-Object { $null -ne $_ })
    $archives = @(
        $assets | Where-Object {
            ([string]$_.name) -cmatch '^minecraftkit-[0-9]+\.[0-9]+\.[0-9]+\.zip$'
        }
    )
    if ($archives.Count -ne 1) {
        throw "Release must contain exactly one minecraftkit-X.Y.Z.zip asset; found $($archives.Count)."
    }
    $archive = $archives[0]
    $archiveName = [string]$archive.name
    if ($archiveName -cnotmatch '^minecraftkit-(?<version>[0-9]+\.[0-9]+\.[0-9]+)\.zip$') {
        throw "Unsafe MinecraftKit archive name: $archiveName"
    }
    $assetVersion = $Matches.version
    $checksumName = "$archiveName.sha256"
    $checksums = @($assets | Where-Object { ([string]$_.name) -ceq $checksumName })
    if ($checksums.Count -ne 1) {
        throw "Release must contain exactly one checksum asset named $checksumName; found $($checksums.Count)."
    }

    $tagName = [string]$Release.tag_name
    if ($tagName -cnotmatch '^v?(?<version>[0-9]+\.[0-9]+\.[0-9]+)$') {
        throw "Release tag does not contain an exact semantic version: $tagName"
    }
    if ($Matches.version -cne $assetVersion) {
        throw "Release tag version $($Matches.version) does not match archive version $assetVersion."
    }
    if ($RequestedVersion -and $RequestedVersion -cne $assetVersion) {
        throw "Requested version $RequestedVersion does not match archive version $assetVersion."
    }
    $archiveBytes = Get-BoundedAssetSize -Asset $archive -Name $archiveName -MaximumBytes $MaximumArchiveBytes
    $checksumBytes = Get-BoundedAssetSize -Asset $checksums[0] -Name $checksumName -MaximumBytes $MaximumChecksumBytes
    return [pscustomobject]@{
        Archive = $archive
        ArchiveName = $archiveName
        ArchiveBytes = $archiveBytes
        Checksum = $checksums[0]
        ChecksumName = $checksumName
        ChecksumBytes = $checksumBytes
        Version = $assetVersion
    }
}

function Copy-ReleaseAsset {
    param(
        [Parameter(Mandatory)]$Asset,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string]$RepositoryName,
        [Parameter(Mandatory)][hashtable]$PublicHeaders,
        [Parameter(Mandatory)][long]$ExpectedBytes,
        [Parameter(Mandatory)][long]$MaximumBytes,
        [string]$FixtureRoot
    )
    if ($FixtureRoot) {
        $source = Join-Path $FixtureRoot $Name
        Assert-DirectChild -Child $source -Parent $FixtureRoot
        if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or (Test-ReparsePoint $source)) {
            throw "Safe fixture asset is missing: $source"
        }
        $sourceBytes = (Get-Item -LiteralPath $source -Force).Length
        if ($sourceBytes -gt $MaximumBytes) {
            throw "Release asset exceeds the $MaximumBytes byte limit for $Name."
        }
        if ($sourceBytes -ne $ExpectedBytes) {
            throw "Release asset size does not match metadata for $Name."
        }
        [IO.File]::Copy($source, $Destination, $false)
        if ((Get-Item -LiteralPath $Destination -Force).Length -ne $ExpectedBytes) {
            throw "Copied release asset size does not match metadata for $Name."
        }
        return
    }

    $downloadUri = Assert-GitHubHttpsUri -Value ([string]$Asset.browser_download_url) -Hosts @('github.com') -Label "Release asset $Name"
    $repositoryPrefix = "/$RepositoryName/releases/download/"
    if (-not $downloadUri.AbsolutePath.StartsWith($repositoryPrefix, [StringComparison]::OrdinalIgnoreCase) -or
        -not $downloadUri.AbsolutePath.EndsWith("/$Name", [StringComparison]::Ordinal)) {
        throw "Release asset URL does not match repository and asset name: $($downloadUri.AbsoluteUri)"
    }

    $currentUri = $downloadUri
    for ($redirectCount = 0; $redirectCount -le $MaximumRedirects; $redirectCount++) {
        $currentUri = Assert-GitHubHttpsUri -Value $currentUri.AbsoluteUri -Hosts $AssetDownloadHosts -Label "Release asset $Name redirect"
        $request = [Net.HttpWebRequest]::Create($currentUri)
        $request.Method = 'GET'
        $request.AllowAutoRedirect = $false
        $request.Timeout = 30000
        $request.ReadWriteTimeout = 30000
        $request.UserAgent = [string]$PublicHeaders['User-Agent']
        $request.Accept = [string]$PublicHeaders.Accept
        $response = $null
        try {
            try {
                $response = [Net.HttpWebResponse]$request.GetResponse()
            }
            catch [Net.WebException] {
                if ($null -eq $_.Exception.Response) { throw }
                $response = [Net.HttpWebResponse]$_.Exception.Response
            }

            $statusCode = [int]$response.StatusCode
            if ($statusCode -ge 300 -and $statusCode -lt 400) {
                if ($redirectCount -ge $MaximumRedirects) {
                    throw "Release asset exceeded the $MaximumRedirects redirect limit: $Name"
                }
                $location = [string]$response.Headers['Location']
                if ([string]::IsNullOrWhiteSpace($location)) {
                    throw "Release asset redirect omitted Location: $Name"
                }
                $nextUri = [Uri]::new($currentUri, $location)
                $currentUri = Assert-GitHubHttpsUri -Value $nextUri.AbsoluteUri -Hosts $AssetDownloadHosts -Label "Release asset $Name redirect"
                continue
            }
            if ($statusCode -ne 200) {
                throw "Release asset request failed with HTTP $statusCode for $Name."
            }

            $contentLength = [long]$response.ContentLength
            if ($contentLength -ge 0) {
                if ($contentLength -gt $MaximumBytes) {
                    throw "Release asset Content-Length exceeds the $MaximumBytes byte limit for $Name."
                }
                if ($contentLength -ne $ExpectedBytes) {
                    throw "Release asset Content-Length does not match metadata for $Name."
                }
            }

            $input = $response.GetResponseStream()
            $output = [IO.FileStream]::new(
                $Destination,
                [IO.FileMode]::CreateNew,
                [IO.FileAccess]::Write,
                [IO.FileShare]::None
            )
            try {
                $buffer = New-Object byte[] 81920
                $downloadedBytes = [long]0
                while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $downloadedBytes += $read
                    if ($downloadedBytes -gt $MaximumBytes) {
                        throw "Release asset download exceeds the $MaximumBytes byte limit for $Name."
                    }
                    $output.Write($buffer, 0, $read)
                }
                $output.Flush()
            }
            finally {
                $output.Dispose()
                $input.Dispose()
            }
            if ($downloadedBytes -ne $ExpectedBytes -or
                (Get-Item -LiteralPath $Destination -Force).Length -ne $ExpectedBytes) {
                throw "Downloaded release asset size does not match metadata for $Name."
            }
            return
        }
        finally {
            if ($null -ne $response) { $response.Dispose() }
        }
    }
    throw "Release asset exceeded the $MaximumRedirects redirect limit: $Name"
}

function Read-StrictChecksum {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ArchiveName,
        [Parameter(Mandatory)][string]$ArchiveVersion
    )
    $bytes = [IO.File]::ReadAllBytes($Path)
    foreach ($value in $bytes) {
        if ($value -gt 127) { throw 'Checksum sidecar must contain ASCII only.' }
    }
    $text = [Text.Encoding]::ASCII.GetString($bytes)
    $match = [regex]::Match(
        $text,
        '\A(?<hash>[0-9A-Fa-f]{64}) {2}(?<name>minecraftkit-(?<version>[0-9]+\.[0-9]+\.[0-9]+)\.zip)\r?\n\z',
        [Text.RegularExpressions.RegexOptions]::CultureInvariant
    )
    if (-not $match.Success) {
        throw 'Checksum sidecar must be one strict SHA-256 record with the exact archive name.'
    }
    if ($match.Groups['name'].Value -cne $ArchiveName -or $match.Groups['version'].Value -cne $ArchiveVersion) {
        throw 'Checksum sidecar archive name or version does not match the selected release asset.'
    }
    return $match.Groups['hash'].Value
}

function Test-FixedTimeHexEqual {
    param(
        [Parameter(Mandatory)][string]$Expected,
        [Parameter(Mandatory)][string]$Actual
    )
    if ($Expected.Length -ne $Actual.Length) { return $false }
    $expectedLower = $Expected.ToLowerInvariant()
    $actualLower = $Actual.ToLowerInvariant()
    $difference = 0
    for ($index = 0; $index -lt $expectedLower.Length; $index++) {
        $difference = $difference -bor (([int][char]$expectedLower[$index]) -bxor ([int][char]$actualLower[$index]))
    }
    return $difference -eq 0
}

function Get-ZipExternalAttributes {
    param([Parameter(Mandatory)]$Entry)
    return [BitConverter]::ToUInt32([BitConverter]::GetBytes([int]$Entry.ExternalAttributes), 0)
}

function Expand-SafeArchive {
    param(
        [Parameter(Mandatory)][string]$ArchivePath,
        [Parameter(Mandatory)][string]$Destination
    )
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $destinationPath = Get-FullPath $Destination
    New-Item -ItemType Directory -Path $destinationPath | Out-Null
    Assert-NoReparseAncestors $destinationPath
    $destinationPrefix = $destinationPath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $archive = [IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        if ($archive.Entries.Count -gt $MaximumArchiveEntries) {
            throw "Archive contains too many entries: $($archive.Entries.Count)"
        }
        $seenEntries = @{}
        $requiredDirectories = @{}
        $expandedBytes = [long]0
        $validatedEntries = [Collections.Generic.List[object]]::new()
        foreach ($entry in $archive.Entries) {
            $entryName = [string]$entry.FullName
            if ([string]::IsNullOrWhiteSpace($entryName) -or $entryName.IndexOf([char]0) -ge 0) {
                throw 'Archive contains an empty or invalid entry name.'
            }
            $normalized = $entryName.Replace('\', '/')
            if ($normalized.Length -ge 240) {
                throw "Archive entry path exceeds the conservative Windows limit: $entryName"
            }
            if ($normalized.StartsWith('/', [StringComparison]::Ordinal) -or
                [IO.Path]::IsPathRooted($entryName) -or $normalized -cmatch '^[A-Za-z]:') {
                throw "Archive contains an absolute path: $entryName"
            }
            $isDirectory = $normalized.EndsWith('/', [StringComparison]::Ordinal)
            $trimmed = $normalized.TrimEnd('/')
            $parts = @($trimmed -split '/')
            if (-not $parts.Count -or $parts[0] -cne 'minecraftkit') {
                throw "Archive entry is outside the canonical minecraftkit root: $entryName"
            }
            foreach ($part in $parts) {
                if ([string]::IsNullOrWhiteSpace($part) -or $part -ceq '.' -or $part -ceq '..') {
                    throw "Archive contains path traversal or an empty segment: $entryName"
                }
                if ($part.Contains(':') -or $part.EndsWith(' ', [StringComparison]::Ordinal) -or
                    $part.EndsWith('.', [StringComparison]::Ordinal) -or
                    $part -match '^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)') {
                    throw "Archive contains a Windows-unsafe path segment: $entryName"
                }
            }
            $relativePath = [string]::Join([IO.Path]::DirectorySeparatorChar, $parts)
            $candidate = Get-FullPath (Join-Path $destinationPath $relativePath)
            if ($candidate.Length -ge 260) {
                throw "Archive destination path exceeds the conservative Windows limit: $entryName"
            }
            if (-not $candidate.StartsWith($destinationPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Archive entry expands outside the temporary directory: $entryName"
            }

            $attributes = Get-ZipExternalAttributes -Entry $entry
            $dosAttributes = $attributes -band 0xFFFF
            $unixType = (($attributes -shr 16) -band 0xF000)
            if (($dosAttributes -band [uint32][IO.FileAttributes]::ReparsePoint) -ne 0 -or $unixType -eq 0xA000) {
                throw "Archive contains a reparse point or symbolic link: $entryName"
            }
            if ($unixType -notin @(0, 0x4000, 0x8000)) {
                throw "Archive contains an unsupported special file: $entryName"
            }
            if (($isDirectory -and $unixType -eq 0x8000) -or (-not $isDirectory -and $unixType -eq 0x4000)) {
                throw "Archive entry type conflicts with its path: $entryName"
            }

            $key = $trimmed.Normalize([Text.NormalizationForm]::FormC).ToLowerInvariant()
            if ($seenEntries.ContainsKey($key)) {
                throw "Archive contains duplicate or case-colliding entries: $entryName"
            }
            $ancestorPath = $parts[0]
            for ($partIndex = 1; $partIndex -lt $parts.Count; $partIndex++) {
                $ancestor = $ancestorPath.Normalize([Text.NormalizationForm]::FormC).ToLowerInvariant()
                if ($seenEntries.ContainsKey($ancestor) -and $seenEntries[$ancestor] -eq 'file') {
                    throw "Archive path descends through a file: $entryName"
                }
                $requiredDirectories[$ancestor] = $true
                $ancestorPath = "$ancestorPath/$($parts[$partIndex])"
            }
            if (-not $isDirectory -and $requiredDirectories.ContainsKey($key)) {
                throw "Archive file collides with an existing directory path: $entryName"
            }
            $seenEntries[$key] = if ($isDirectory) { 'directory' } else { 'file' }
            if ($isDirectory) { $requiredDirectories[$key] = $true }

            if (-not $isDirectory) {
                $entryLength = [long]$entry.Length
                if ($entryLength -lt 0) { throw "Archive entry has an invalid size: $entryName" }
                if ($entryLength -gt ([long]$MaximumExpandedBytes - $expandedBytes)) {
                    throw "Archive expands beyond the $MaximumExpandedBytes byte safety limit."
                }
                $expandedBytes += $entryLength
            }
            $validatedEntries.Add([pscustomobject]@{
                Entry = $entry
                Destination = $candidate
                IsDirectory = $isDirectory
            })
        }

        foreach ($validated in $validatedEntries) {
            if ($validated.IsDirectory) {
                New-Item -ItemType Directory -Path $validated.Destination -Force | Out-Null
                continue
            }
            $parent = Split-Path -Parent $validated.Destination
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            $input = $validated.Entry.Open()
            $output = [IO.FileStream]::new(
                $validated.Destination,
                [IO.FileMode]::CreateNew,
                [IO.FileAccess]::Write,
                [IO.FileShare]::None
            )
            try {
                $buffer = New-Object byte[] 81920
                $written = [long]0
                while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $written += $read
                    if ($written -gt [long]$validated.Entry.Length) {
                        throw "Archive entry expands beyond its declared size: $($validated.Entry.FullName)"
                    }
                    $output.Write($buffer, 0, $read)
                }
                if ($written -ne [long]$validated.Entry.Length) {
                    throw "Archive entry size does not match its declaration: $($validated.Entry.FullName)"
                }
                $output.Flush()
            }
            finally {
                $output.Dispose()
                $input.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
    }

    Assert-PhysicalTree $destinationPath
    $candidates = @(
        Get-ChildItem -LiteralPath $destinationPath -Directory -Recurse -Force |
            Where-Object {
                $_.Name -ceq 'minecraftkit' -and
                (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf) -and
                (Test-Path -LiteralPath (Join-Path $_.FullName 'scripts\install-global.ps1') -PathType Leaf)
            }
    )
    if ($candidates.Count -ne 1) {
        throw "Archive must contain exactly one canonical MinecraftKit package root; found $($candidates.Count)."
    }
    $canonicalRoot = Get-FullPath $candidates[0].FullName
    Assert-DirectChild -Child $canonicalRoot -Parent $destinationPath
    return $canonicalRoot
}

if ($AllowTestSource -and [string]::IsNullOrWhiteSpace($TestReleaseDirectory)) {
    throw '-AllowTestSource requires -TestReleaseDirectory.'
}
if (-not $AllowTestSource -and -not [string]::IsNullOrWhiteSpace($TestReleaseDirectory)) {
    throw '-TestReleaseDirectory is disabled unless -AllowTestSource is explicitly supplied.'
}

$repositoryParts = @($Repository -split '/')
if ($repositoryParts.Count -ne 2 -or $repositoryParts[0] -in @('.', '..') -or $repositoryParts[1] -in @('.', '..')) {
    throw "Unsafe GitHub repository name: $Repository"
}
$escapedOwner = [Uri]::EscapeDataString($repositoryParts[0])
$escapedRepository = [Uri]::EscapeDataString($repositoryParts[1])
$apiUrl = if ($Version) {
    "https://api.github.com/repos/$escapedOwner/$escapedRepository/releases/tags/v$Version"
}
else {
    "https://api.github.com/repos/$escapedOwner/$escapedRepository/releases/latest"
}
$apiUri = Assert-GitHubHttpsUri -Value $apiUrl -Hosts @('api.github.com') -Label 'GitHub release API'
$fixtureRoot = $null
if ($AllowTestSource) {
    $fixtureRoot = Get-FullPath $TestReleaseDirectory
    Assert-NoReparseAncestors $fixtureRoot
    Assert-PhysicalTree $fixtureRoot
}

[Net.ServicePointManager]::SecurityProtocol =
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$headers = Get-GitHubHeaders
$assetHeaders = Get-PublicAssetHeaders -ApiHeaders $headers
$release = Read-ReleaseMetadata -ApiUri $apiUri -Headers $headers -FixtureRoot $fixtureRoot
$selection = Select-ReleaseAssets -Release $release -RequestedVersion $Version

$temporaryParent = Get-FullPath ([IO.Path]::GetTempPath())
Assert-NoReparseAncestors $temporaryParent
$temporaryDirectory = Join-Path $temporaryParent "mk-$([guid]::NewGuid().ToString('N'))"
Assert-DirectChild -Child $temporaryDirectory -Parent $temporaryParent
try {
    New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
    $archivePath = Join-Path $temporaryDirectory $selection.ArchiveName
    $checksumPath = Join-Path $temporaryDirectory $selection.ChecksumName
    Assert-DirectChild -Child $archivePath -Parent $temporaryDirectory
    Assert-DirectChild -Child $checksumPath -Parent $temporaryDirectory
    Copy-ReleaseAsset -Asset $selection.Archive -Name $selection.ArchiveName -Destination $archivePath -RepositoryName $Repository -PublicHeaders $assetHeaders -ExpectedBytes $selection.ArchiveBytes -MaximumBytes $MaximumArchiveBytes -FixtureRoot $fixtureRoot
    Copy-ReleaseAsset -Asset $selection.Checksum -Name $selection.ChecksumName -Destination $checksumPath -RepositoryName $Repository -PublicHeaders $assetHeaders -ExpectedBytes $selection.ChecksumBytes -MaximumBytes $MaximumChecksumBytes -FixtureRoot $fixtureRoot

    $expectedHash = Read-StrictChecksum -Path $checksumPath -ArchiveName $selection.ArchiveName -ArchiveVersion $selection.Version
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
    if (-not (Test-FixedTimeHexEqual -Expected $expectedHash -Actual $actualHash)) {
        throw "SHA-256 checksum mismatch for $($selection.ArchiveName)."
    }

    $extractRoot = Join-Path $temporaryDirectory 'extracted'
    Assert-DirectChild -Child $extractRoot -Parent $temporaryDirectory
    $packageRoot = Expand-SafeArchive -ArchivePath $archivePath -Destination $extractRoot
    $installer = Join-Path $packageRoot 'scripts\install-global.ps1'
    $installerArguments = @{
        SourceRoot = $packageRoot
        Target = $Target
        CodexSkillsRoot = $CodexSkillsRoot
        ClaudeSkillsRoot = $ClaudeSkillsRoot
        ClaudeCommandsRoot = $ClaudeCommandsRoot
        Python = $Python
    }
    if ($PlanOnly) { $installerArguments.PlanOnly = $true }
    $installerText = [IO.File]::ReadAllText($installer, [Text.Encoding]::UTF8)
    $installerScript = [scriptblock]::Create($installerText)
    & $installerScript @installerArguments
}
finally {
    if (Test-Path -LiteralPath $temporaryDirectory) {
        Assert-DirectChild -Child $temporaryDirectory -Parent $temporaryParent
        Assert-PhysicalTree $temporaryDirectory
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
