; WorkforceOptimizer.iss
[Setup]
AppName=Workforce Optimizer
AppVersion=1.0
AppPublisher=Christopher Petitpas
DefaultDirName={autopf}\Workforce Optimizer
DefaultGroupName=Workforce Optimizer
OutputDir=output
OutputBaseFilename=WorkforceOptimizer_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=icons\teamwork.ico
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\WorkforceOptimizer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\Workforce Optimizer"; Filename: "{app}\WorkforceOptimizer.exe"
Name: "{group}\Workforce Optimizer"; Filename: "{app}\WorkforceOptimizer.exe"
Name: "{group}\Uninstall Workforce Optimizer"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\WorkforceOptimizer.exe"; Description: "Launch Workforce Optimizer"; Flags: nowait postinstall skipifsilent

; -----------------------------------------------------------------
; 4. Extract bundled sample CSVs → %LOCALAPPDATA%\Workforce Optimizer\data
; -----------------------------------------------------------------
[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ExePath, TempDir, DataSrc, DataDst, FileName: String;
  FindRec: TFindRec;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    ExePath := ExpandConstant('{app}\WorkforceOptimizer.exe');
    TempDir := GetTempDir + '\WorkforceOptimizer_data';
    DataDst := ExpandConstant('{userappdata}\Workforce Optimizer\data');

    // 1. Extract bundled "data" folder to temp
    if not DirExists(TempDir) then CreateDir(TempDir);
    if Exec(ExePath, '--extract-data "' + TempDir + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      // 2. Copy from temp → real user folder (only if empty)
      if not DirExists(DataDst) then CreateDir(DataDst);
      if DirExists(TempDir + '\data') then
      begin
        if FindFirst(TempDir + '\data\*.*', FindRec) then
        begin
          try
            repeat
              if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
              begin
                FileName := FindRec.Name;
                if not FileExists(DataDst + '\' + FileName) then
                  FileCopy(TempDir + '\data\' + FileName, DataDst + '\' + FileName, False);
              end;
            until not FindNext(FindRec);
          finally
            FindClose(FindRec);
          end;
        end;
      end;
    end;
    // Clean up temp
    DelTree(TempDir, True, True, True);
  end;
end;