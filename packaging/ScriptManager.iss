#define MyAppName "Script Manager"
#define MyAppExeName "ScriptManager.exe"
#define MyAppPublisher "Script Manager"
#define MyAppProgId "ScriptManager.Project"

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

[Setup]
AppId={{A4E2C1C2-51AA-4EB8-985B-6B27E473381D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Script Manager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\installer-dist
OutputBaseFilename=ScriptManager-{#MyAppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
#ifexist "..\resources\app.ico"
SetupIconFile=..\resources\app.ico
#endif
ChangesAssociations=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\ScriptManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\resources\project_file.ico"; DestDir: "{app}\resources"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Registry]
Root: HKCU; Subkey: "Software\Classes\.smproj"; ValueType: string; ValueName: ""; ValueData: "{#MyAppProgId}"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#MyAppProgId}"; ValueType: string; ValueName: ""; ValueData: "Script Management Project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#MyAppProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\resources\project_file.ico"
Root: HKCU; Subkey: "Software\Classes\{#MyAppProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
