$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ProgressPreference = "SilentlyContinue"

$articleId = 22687585
$destination = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..\data\raw\ddxplus_data")
)
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem

$article = Invoke-RestMethod -Uri "https://api.figshare.com/v2/articles/$articleId"
if ($article.id -ne $articleId -or -not $article.is_public) {
    throw "Figshare returned unexpected or non-public article metadata for $articleId."
}

foreach ($file in $article.files) {
    if ($file.is_link_only) {
        throw "Required Figshare asset '$($file.name)' is a link-only file."
    }
    if ([System.IO.Path]::GetFileName($file.name) -ne $file.name) {
        throw "Unsafe asset filename returned by Figshare: '$($file.name)'."
    }

    $target = Join-Path $destination $file.name
    $valid = $false
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $existing = Get-Item -LiteralPath $target
        if ($existing.Length -eq $file.size) {
            $hash = (Get-FileHash -LiteralPath $target -Algorithm MD5).Hash.ToLowerInvariant()
            $valid = $hash -eq $file.computed_md5.ToLowerInvariant()
        }
    }

    if (-not $valid) {
        $download = "$target.download"
        try {
            Invoke-WebRequest -Uri $file.download_url -OutFile $download -UseBasicParsing
            $downloaded = Get-Item -LiteralPath $download
            $hash = (Get-FileHash -LiteralPath $download -Algorithm MD5).Hash.ToLowerInvariant()
            if ($downloaded.Length -ne $file.size -or $hash -ne $file.computed_md5.ToLowerInvariant()) {
                throw "Downloaded asset '$($file.name)' failed size or MD5 verification."
            }
            Move-Item -LiteralPath $download -Destination $target -Force
            Write-Host "Downloaded and verified $($file.name) ($($file.size) bytes)"
        }
        finally {
            if (Test-Path -LiteralPath $download) {
                Remove-Item -LiteralPath $download -Force
            }
        }
    }
    else {
        Write-Host "Already verified $($file.name) ($($file.size) bytes)"
    }

    if ([System.IO.Path]::GetExtension($file.name).ToLowerInvariant() -ne ".zip") {
        continue
    }

    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.name)
    $csvPath = Join-Path $destination "$baseName.csv"
    $temporaryCsv = "$csvPath.tmp"
    $archive = [System.IO.Compression.ZipFile]::OpenRead($target)
    try {
        $entries = @($archive.Entries | Where-Object { -not $_.FullName.EndsWith("/") })
        if ($entries.Count -ne 1 -or $entries[0].Name -ne $baseName) {
            throw "Unexpected contents in '$($file.name)': expected one '$baseName' data file."
        }

        $inputStream = $entries[0].Open()
        $outputStream = [System.IO.File]::Open(
            $temporaryCsv,
            [System.IO.FileMode]::Create,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            $inputStream.CopyTo($outputStream)
        }
        finally {
            $outputStream.Dispose()
            $inputStream.Dispose()
        }
    }
    finally {
        $archive.Dispose()
    }

    try {
        if ((Get-Item -LiteralPath $temporaryCsv).Length -eq 0) {
            throw "Extracted data file '$($file.name)' is empty."
        }
        Move-Item -LiteralPath $temporaryCsv -Destination $csvPath -Force
        Write-Host "Extracted $($file.name) to $csvPath"
    }
    finally {
        if (Test-Path -LiteralPath $temporaryCsv) {
            Remove-Item -LiteralPath $temporaryCsv -Force
        }
    }
}

Write-Host "DDXPlus article $articleId is verified and extracted in $destination"
