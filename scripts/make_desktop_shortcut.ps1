# Recreate the desktop shortcut to the project on the user's REAL desktop
# (OneDrive-redirected on this machine). WScript.Shell rejects non-ASCII TargetPath
# and fails to save directly into the OneDrive folder, so: resolve the 8.3 short
# path via FSO, save to %TEMP%, then move into place. Pure ASCII source on purpose
# (Windows PowerShell 5.1 misreads non-BOM UTF-8); Chinese strings are char codes.
$name = (-join [char[]](0x7F18, 0x7F18, 0x684C, 0x5BA0))  # "缘缘桌宠"
$fso = New-Object -ComObject Scripting.FileSystemObject
$f = $fso.GetFolder('C:\Users\lenovo\Desktop\' + $name)
$target = $f.ShortPath
if ($target -match '[^\x00-\x7F]') { $target = 'C:\Users\lenovo\Desktop' }  # no 8.3 fallback

$ws = New-Object -ComObject WScript.Shell
$tmp = Join-Path $env:TEMP 'yuanyuan-shortcut.lnk'
$s = $ws.CreateShortcut($tmp)
$s.TargetPath = $target
$s.Description = 'Yuanyuan desktop pet project'
$s.Save()

$desktop = [Environment]::GetFolderPath('Desktop')
$dst = Join-Path $desktop ($name + '.lnk')
Remove-Item -Force -ErrorAction SilentlyContinue $dst
Move-Item -Force $tmp $dst
Write-Output ('target=' + $target)
Write-Output ('created: ' + (Test-Path $dst))
