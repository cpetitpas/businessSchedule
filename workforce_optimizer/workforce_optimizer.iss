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
Source: "dist\WorkforceOptimizer.exe"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{autodesktop}\Workforce Optimizer"; Filename: "{app}\WorkforceOptimizer.exe"
Name: "{group}\Workforce Optimizer"; Filename: "{app}\WorkforceOptimizer.exe"
Name: "{group}\Uninstall Workforce Optimizer"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\WorkforceOptimizer.exe"; Description: "Launch Workforce Optimizer"; Flags: postinstall