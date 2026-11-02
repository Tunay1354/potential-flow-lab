; installer.iss — the Windows installer of the program (Inno Setup 6; ROADMAP 24.2). It packs the folder that
; PyInstaller made (dist\<AppName>\) into one Setup.exe. GitHub builds it (.github/workflows/windows-build.yml):
;     iscc /DAppName=… /DAppVersion=… /DPublisher=… /DSubtitle=… /DSourceDir=dist\Flowy /DIconFile=… installer.iss
; The names come from app_info.py (never written here).
;
; What it does: asks the language (English / Türkçe), for whom (only me: no administrator needed / all users),
; where, the Start menu folder (or none), a desktop shortcut, opening .pflow files with the program, starting it
; with Windows; closes a running copy before an update; an update keeps the folder and settings (old program
; files are removed first); Apps & features shows the name, version, publisher and icon; at the end "Launch".
; The uninstaller removes the program, its shortcuts and the .pflow link, and asks whether to delete the user's
; settings and data too (recent files, autosaved scenes, logs, the compiled kernels) — scene files (.pflow) the
; user saved are never touched.

#ifndef AppName
  #error Pass the names from app_info.py: /DAppName=… /DAppVersion=… /DPublisher=… /DSubtitle=…
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\" + AppName
#endif
#ifndef IconFile
  #error Pass the icon: /DIconFile=… (PyInstaller's build folder has it: build\build_exe\<AppName>.ico)
#endif
#define ExeName AppName + ".exe"
#define ProgId AppName + ".Scene"

[Setup]
AppId={{6E2F4C3A-9B1D-4E7F-A85C-3D9E1B7F2A64}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppComments={#Subtitle}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} — {#Subtitle} (setup)
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UsePreviousAppDir=yes
DisableDirPage=no
DisableProgramGroupPage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#ExeName}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2/max
SolidCompression=yes
OutputBaseFilename={#AppName}-v{#AppVersion}-setup

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"

[CustomMessages]
en.AssocTask=Open .pflow scene files with %1 (double-click)
tr.AssocTask=.pflow sahne dosyalarını %1 ile aç (çift tıklama)
en.StartupTask=Start %1 when Windows starts
tr.StartupTask=Windows açılınca %1 programını başlat
en.OtherTasks=Other:
tr.OtherTasks=Diğer:
en.SceneFile=%1 scene
tr.SceneFile=%1 sahnesi
en.DeleteData=Also delete your %1 settings and data?%n%nSettings, the recent files list, autosaved scenes, logs and the compiled fast kernels.%nScene files (.pflow) you saved are never deleted.%n%nNo: they stay for a later installation.
tr.DeleteData=%1 ayarların ve verilerin de silinsin mi?%n%nAyarlar, son dosyalar listesi, otomatik kaydedilen sahneler, log'lar ve derlenmiş hızlı çekirdekler.%nKaydettiğin sahne dosyaları (.pflow) asla silinmez.%n%nHayır: sonraki bir kurulum için kalırlar.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "{cm:AssocTask,{#AppName}}"; GroupDescription: "{cm:OtherTasks}"
Name: "startup"; Description: "{cm:StartupTask,{#AppName}}"; GroupDescription: "{cm:OtherTasks}"; Flags: unchecked

[InstallDelete]
; an update: the old program files go first (no stale files of an older version)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"; Comment: "{#Subtitle}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Comment: "{#Subtitle}"; Tasks: desktopicon

[Registry]
; .pflow → the program (per user or for all users, as installed: HKA)
Root: HKA; Subkey: "Software\Classes\.pflow\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.pflow"; ValueType: string; ValueName: ""; ValueData: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "{cm:SceneFile,{#AppName}}"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#ExeName},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#ExeName}"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#ExeName}\SupportedTypes"; ValueType: string; ValueName: ".pflow"; ValueData: ""; Flags: uninsdeletekey; Tasks: assoc
; start with Windows (this user)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#ExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
{ The user's data (the same places as the program uses: app/paths.py, QSettings, Numba's cache). }
procedure DeleteUserData;
var
  Cache: String;
  Found: TFindRec;
begin
  DelTree(ExpandConstant('{localappdata}\{#Publisher}\{#AppName}'), True, True, True);
  RemoveDir(ExpandConstant('{localappdata}\{#Publisher}'));                   { only if empty now }
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\{#Publisher}\{#AppName}');
  RegDeleteKeyIfEmpty(HKCU, 'Software\{#Publisher}');
  Cache := ExpandConstant('{localappdata}\numba\Cache');                     { the program's compiled kernels }
  if FindFirst(Cache + '\physics_*', Found) then
  try
    repeat
      if Found.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
        DelTree(Cache + '\' + Found.Name, True, True, True);
    until not FindNext(Found);
  finally
    FindClose(Found);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    if MsgBox(ExpandConstant('{cm:DeleteData,{#AppName}}'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DeleteUserData;
end;
