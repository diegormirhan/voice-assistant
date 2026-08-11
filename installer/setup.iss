; Inno Setup script — VoiceAssistant installer.
; Builds the PyInstaller output (dist\VoiceAssistant\) into a single installer.

#define MyAppName "VoiceAssistant"
#define MyAppVersion "1.0.0"
#define MyAppExeName "VoiceAssistant.exe"

[Setup]
AppId={{A7B0D5C3-4E2F-4B1A-9C6D-8F3E2A1B7C4D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=VoiceAssistant
DefaultDirName={localappdata}\VoiceAssistant
DefaultGroupName=VoiceAssistant
OutputDir=output
OutputBaseFilename=VoiceAssistantSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\VoiceAssistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent
