; Inno Setup-script: maakt DMXDesk-Setup.exe van de map dist\DMXDesk (na packaging\bouw.py).
; Bouwen: iscc /DVersie=2.0.0 /DUitvoer=dist\uitvoer packaging\windows-installer.iss

#ifndef Versie
  #define Versie "2.0.0"
#endif
#ifndef Uitvoer
  #define Uitvoer "..\dist\uitvoer"
#endif

[Setup]
AppId={{7B0E5B3C-2F7D-4C44-9C1E-2D0A6B3F9D11}
AppName=DMXDesk
AppVersion={#Versie}
AppPublisher=DMXDesk
DefaultDirName={autopf}\DMXDesk
DefaultGroupName=DMXDesk
DisableProgramGroupPage=yes
OutputDir={#Uitvoer}
OutputBaseFilename=DMXDesk-{#Versie}-windows-installer
SetupIconFile=icoon.ico
UninstallDisplayIcon={app}\DMXDesk.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "bureaublad"; Description: "Snelkoppeling op het bureaublad"; GroupDescription: "Extra:"

[Files]
Source: "..\dist\DMXDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DMXDesk"; Filename: "{app}\DMXDesk.exe"
Name: "{autodesktop}\DMXDesk"; Filename: "{app}\DMXDesk.exe"; Tasks: bureaublad

[Run]
Filename: "{app}\DMXDesk.exe"; Description: "DMXDesk starten"; Flags: nowait postinstall skipifsilent
