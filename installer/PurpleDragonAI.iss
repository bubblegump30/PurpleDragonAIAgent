#define AppVersion "1.7.0"
[Setup]
AppId=PurpleDragonAIAgent
AppName=Purple Dragon AI Agent
AppVersion={#AppVersion}
AppPublisher=KyleAustin85
DefaultDirName={localappdata}\Programs\PurpleDragonAIAgent
DefaultGroupName=Purple Dragon AI Agent
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=PurpleDragonAI-{#AppVersion}-Setup-x64
SetupIconFile=..\assets\purple_dragon_ai.ico
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
[Files]
Source: "..\dist\PurpleDragonAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Purple Dragon AI Agent"; Filename: "{app}\PurpleDragonAI.exe"; WorkingDir: "{app}"
Name: "{group}\Recover Settings"; Filename: "{app}\PurpleDragonRecovery.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\PurpleDragonAI.exe"; Description: "Open Purple Dragon AI Agent"; Flags: nowait postinstall skipifsilent
; Runtime settings, vault, logs and workspace are not installer inputs and have no UninstallDelete rule.
