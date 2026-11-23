' Runs Nova AI completely silently in the background with zero terminal popup
Set WshShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run """" & strPath & "\Run_Nova_AI.bat""", 0, False
Set WshShell = Nothing
