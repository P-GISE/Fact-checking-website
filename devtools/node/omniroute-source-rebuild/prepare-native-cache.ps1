param([Parameter(Mandatory=$true)][string]$CachePath, [Parameter(Mandatory=$true)][string]$ProfilePath)
$ErrorActionPreference = 'Stop'
$targetPath = [IO.Path]::GetFullPath($CachePath)
$expectedPath = [IO.Path]::GetFullPath((Join-Path $ProfilePath '.pocketbook-security-swc-20261026'))
if ($targetPath -ne $expectedPath) { throw 'private native cache path mismatch' }
$directory = Get-Item -LiteralPath $targetPath
if (($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'private native cache cannot be a reparse point' }
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
$acl.SetOwner($ownerSid)
foreach ($sid in @($ownerSid.Value,'S-1-5-18','S-1-5-32-544')) {
  $rule = [Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow')
  $acl.AddAccessRule($rule)
}
[IO.FileSystemAclExtensions]::SetAccessControl([IO.DirectoryInfo]::new($targetPath),$acl)
