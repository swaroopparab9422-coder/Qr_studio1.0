; Inno Setup script - builds installer\QR_Studio_Setup.exe from dist\QR Studio
[Setup]
AppName=QR Studio
AppVersion=1.0.0
AppPublisher=QR Studio
DefaultDirName={autopf}\QR Studio
DefaultGroupName=QR Studio
OutputDir=installer
OutputBaseFilename=QR_Studio_Setup
SetupIconFile=assets\icons\app.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\QR Studio.exe

[Files]
Source: "dist\QR Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\QR Studio"; Filename: "{app}\QR Studio.exe"
Name: "{autodesktop}\QR Studio"; Filename: "{app}\QR Studio.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\QR Studio.exe"; Description: "Start QR Studio"; Flags: nowait postinstall skipifsilent
