param([string]$Mode,[string]$State)
$ErrorActionPreference='Stop'
$b5State=Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
if($Mode -eq 'protect') {
  $b5Sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
  foreach($b5Row in $b5State.roots) {
    $b5Acl=Get-Acl -LiteralPath $b5Row.path
    $b5Row.sddl=$b5Acl.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::All)
  }
  $b5State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $State -Encoding UTF8
  foreach($b5Row in $b5State.roots) {
    $b5Acl=Get-Acl -LiteralPath $b5Row.path
    $b5Rights=[System.Security.AccessControl.FileSystemRights]::Write -bor [System.Security.AccessControl.FileSystemRights]::Delete -bor [System.Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles
    $b5Rule=[System.Security.AccessControl.FileSystemAccessRule]::new($b5Sid,$b5Rights,([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),[System.Security.AccessControl.PropagationFlags]::None,[System.Security.AccessControl.AccessControlType]::Deny)
    $b5Acl.AddAccessRule($b5Rule);Set-Acl -LiteralPath $b5Row.path -AclObject $b5Acl
  }
} elseif($Mode -eq 'restore') {
  foreach($b5Row in $b5State.roots) {
    if(-not $b5Row.sddl) { throw 'MISSING_ORIGINAL_TEST_ACL' }
    $b5Acl=Get-Acl -LiteralPath $b5Row.path
    $b5Acl.SetSecurityDescriptorSddlForm($b5Row.sddl,[System.Security.AccessControl.AccessControlSections]::Access)
    Set-Acl -LiteralPath $b5Row.path -AclObject $b5Acl
    $b5After=(Get-Acl -LiteralPath $b5Row.path).GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::All)
    if($b5After -ne $b5Row.sddl) { throw 'TEST_GUARD_ACL_RESTORE_UNCONFIRMED' }
  }
} else { throw 'UNKNOWN_TEST_GUARD_MODE' }
