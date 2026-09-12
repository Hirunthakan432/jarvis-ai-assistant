#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
[Setup]
AppId={{92D255B1-7529-4A17-B127-535B5218A760}
AppName=Jarvis AI Assistant
AppVersion={#AppVersion}
AppPublisher=Hirunthakan
DefaultDirName={localappdata}\Programs\Jarvis
DefaultGroupName=Jarvis AI Assistant
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installers
OutputBaseFilename=Jarvis-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Jarvis.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Jarvis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Jarvis AI Assistant"; Filename: "{app}\Jarvis.exe"
Name: "{autodesktop}\Jarvis AI Assistant"; Filename: "{app}\Jarvis.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Jarvis.exe"; Description: "Launch Jarvis"; Flags: nowait postinstall skipifsilent
