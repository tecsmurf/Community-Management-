; Inno Setup script: turns dist\CommunityManager into CommunityManager-Setup.exe
; Build with:  iscc packaging\installer.iss   (run from the repository root)

#define AppName "Community Manager"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F1B6C1E-6A0B-4C55-9E57-3B0C2A7D9A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Ambesh Guru Shwetambar Jain Samaj
DefaultDirName={localappdata}\Programs\CommunityManager
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=CommunityManager-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\CommunityManager\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\CommunityManager.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\CommunityManager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CommunityManager.exe"; Description: "Open {#AppName} now"; Flags: nowait postinstall skipifsilent

; The database lives in %APPDATA%\CommunityManager and is NOT removed on uninstall,
; so reinstalling or upgrading keeps all data.
