; Candidato local Windows. O mesmo bundle PyInstaller tambem pode ser usado sem instalacao.
[Setup]
AppId=KindlePDF.BoniJr
AppName=KindlePDF
AppVersion=0.6.3
AppPublisher=Boni Jr
DefaultDirName={localappdata}\Programs\KindlePDF
DefaultGroupName=KindlePDF
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
WizardStyle=modern dynamic
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\KindlePDF.exe
OutputDir=..\artifacts
OutputBaseFilename=KindlePDF-Setup-win-x64-candidate

[Files]
Source: "..\dist\KindlePDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\KindlePDF"; Filename: "{app}\KindlePDF.exe"; WorkingDir: "{app}"
