Option Explicit

Dim shell, fso, root, pythonw, candidates, candidate, index, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

candidates = Array( _
    root & "\.venv-local-translate\Scripts\pythonw.exe", _
    shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Python\pythoncore-3.14-64\pythonw.exe", _
    shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Python\pythoncore-3.11-64\pythonw.exe")

pythonw = ""
For index = 0 To UBound(candidates)
    candidate = candidates(index)
    If fso.FileExists(candidate) Then
        pythonw = candidate
        Exit For
    End If
Next

If pythonw = "" Then
    MsgBox "Python 3 (pythonw.exe) was not found. Install Python 3 or run setup_local_translation.bat.", _
        vbCritical, "Unable to start GitHub Ranking"
    WScript.Quit 1
End If

command = Chr(34) & pythonw & Chr(34) & " " & _
    Chr(34) & root & "\ranking_launcher.py" & Chr(34)
shell.Run command, 0, False
