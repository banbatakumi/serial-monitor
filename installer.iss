; Serial Monitor - Windows Installer Script (Inno Setup 6)
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

[Setup]
AppName=Serial Monitor
AppVersion={#MyAppVersion}
AppPublisher=banbatakumi
AppPublisherURL=https://github.com/banbatakumi/serial-monitor
AppSupportURL=https://github.com/banbatakumi/serial-monitor/issues
DefaultDirName={autopf}\SerialMonitor
DefaultGroupName=Serial Monitor
OutputDir=dist
OutputBaseFilename=SerialMonitor-{#MyAppVersion}-Windows
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\SerialMonitor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Serial Monitor"; Filename: "{app}\SerialMonitor.exe"
Name: "{group}\{cm:UninstallProgram,Serial Monitor}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Serial Monitor"; Filename: "{app}\SerialMonitor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SerialMonitor.exe"; Description: "{cm:LaunchProgram,Serial Monitor}"; Flags: nowait postinstall skipifsilent
