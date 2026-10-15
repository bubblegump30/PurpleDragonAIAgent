param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [string]$ExpectedSHA256
)
$ErrorActionPreference = 'Stop'
$Item = Get-Item -LiteralPath $Archive
if ($Item.PSIsContainer) { throw 'Choose a file.' }
$Actual = (Get-FileHash -LiteralPath $Item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output "SHA-256: $Actual"
if ([string]::IsNullOrWhiteSpace($ExpectedSHA256)) {
    Write-Output 'Calculated only. No expected hash was provided; publisher identity has not been verified.'
    exit 0
}
if ($ExpectedSHA256 -notmatch '^[a-fA-F0-9]{64}$') { throw 'ExpectedSHA256 must be exactly 64 hexadecimal characters.' }
if ($Actual -ne $ExpectedSHA256.ToLowerInvariant()) { throw 'Hash mismatch. The file differs from the expected bytes.' }
Write-Output 'Hash matches. This verifies byte equality only; trust depends on where the expected hash came from.'
