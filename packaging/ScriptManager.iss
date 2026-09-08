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

[Code]
const
  GoogleDriveUninstallSubkey = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{6BBAE539-2232-434A-A4E5-9A33560C6283}';
  GoogleDriveDownloadUrl = 'https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe';
  GoogleDriveHelpUrl = 'https://support.google.com/drive/answer/10838124';

var
  GoogleDrivePage: TInputOptionWizardPage;
  GoogleDriveHelpButton: TNewButton;

function IsGoogleDriveInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM32, GoogleDriveUninstallSubkey);
  if IsWin64 and (not Result) then
    Result := RegKeyExists(HKLM64, GoogleDriveUninstallSubkey);
end;

function SkipGoogleDrivePrerequisite: Boolean;
var
  ParamValue: String;
begin
  ParamValue := ExpandConstant('{param:SKIPDRIVEPREREQ|0}');
  Result := IsSilent or (CompareText(ParamValue, '1') = 0) or IsGoogleDriveInstalled;
end;

procedure OpenGoogleDriveHelp(Sender: TObject);
var
  ErrorCode: Integer;
begin
  if not ShellExec('open', GoogleDriveHelpUrl, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode) then
    MsgBox(
      'Halaman Google Drive tidak dapat dibuka. Buka secara manual:' + #13#10 +
      GoogleDriveHelpUrl,
      mbInformation,
      MB_OK
    );
end;

function OnGoogleDriveDownloadProgress(
  const Url, FileName: String;
  const Progress, ProgressMax: Int64
): Boolean;
begin
  if ProgressMax > 0 then
    WizardForm.StatusLabel.Caption := Format(
      'Mengunduh Google Drive for desktop... %d%%',
      [(Progress * 100) div ProgressMax]
    )
  else
    WizardForm.StatusLabel.Caption := 'Mengunduh Google Drive for desktop...';
  Result := True;
end;

function InstallGoogleDrive: Boolean;
var
  InstallerPath: String;
  ResultCode: Integer;
  ContinueChoice: Integer;
begin
  Result := False;
  WizardForm.NextButton.Enabled := False;

  try
    WizardForm.StatusLabel.Caption := 'Mengunduh installer resmi Google...';
    DownloadTemporaryFile(
      GoogleDriveDownloadUrl,
      'GoogleDriveSetup.exe',
      '',
      @OnGoogleDriveDownloadProgress
    );

    InstallerPath := ExpandConstant('{tmp}\GoogleDriveSetup.exe');
    WizardForm.StatusLabel.Caption := 'Menginstal Google Drive for desktop...';

    if not Exec(
      InstallerPath,
      '--silent --gsuite_shortcuts=false',
      ExpandConstant('{tmp}'),
      SW_SHOWNORMAL,
      ewWaitUntilTerminated,
      ResultCode
    ) then
    begin
      MsgBox(
        'Installer Google Drive tidak dapat dijalankan. ' +
        'Anda dapat mencobanya lagi atau memilih opsi untuk mengaturnya sendiri.',
        mbError,
        MB_OK
      );
      Exit;
    end;

    if ResultCode <> 0 then
    begin
      MsgBox(
        Format(
          'Instalasi Google Drive belum berhasil diselesaikan (kode %d).' + #13#10 +
          'Silakan coba lagi atau pilih opsi untuk mengaturnya sendiri.',
          [ResultCode]
        ),
        mbError,
        MB_OK
      );
      Exit;
    end;

    if IsGoogleDriveInstalled then
    begin
      WizardForm.StatusLabel.Caption := 'Google Drive for desktop berhasil dipasang.';
      Result := True;
      Exit;
    end;

    ContinueChoice := MsgBox(
      'Installer Google Drive telah selesai, tetapi instalasinya belum dapat ' +
      'dikonfirmasi dari Windows.' + #13#10 + #13#10 +
      'Anda tetap dapat menginstal Script Manager dan menyelesaikan Google Drive nanti.' + #13#10 + #13#10 +
      'Lanjutkan instalasi Script Manager?',
      mbConfirmation,
      MB_YESNO
    );
    Result := ContinueChoice = IDYES;
  except
    MsgBox(
      'Google Drive for desktop tidak dapat diunduh atau dipasang.' + #13#10 + #13#10 +
      GetExceptionMessage + #13#10 + #13#10 +
      'Periksa koneksi internet, coba lagi, atau pilih opsi untuk mengaturnya sendiri.',
      mbError,
      MB_OK
    );
  end;

  WizardForm.NextButton.Enabled := True;
end;

procedure InitializeWizard;
begin
  GoogleDrivePage := CreateInputOptionPage(
    wpWelcome,
    'Google Drive for desktop',
    'Siapkan akses folder Google Drive',
    'Script Manager menggunakan Google Drive for desktop agar folder proyek di Google Drive dapat diakses seperti folder biasa di Windows.' + #13#10 + #13#10 +
    'Jika belum terpasang, installer resmi Google dapat diunduh langsung dari Google. Login akun tetap dilakukan melalui Google Drive sendiri.',
    True,
    False
  );

  GoogleDrivePage.Add('Install Google Drive & Lanjut');
  GoogleDrivePage.Add('Saya akan mengaturnya sendiri');
  GoogleDrivePage.SelectedValueIndex := 0;

  GoogleDriveHelpButton := TNewButton.Create(GoogleDrivePage);
  GoogleDriveHelpButton.Parent := GoogleDrivePage.Surface;
  GoogleDriveHelpButton.Caption := 'Buka panduan Google Drive';
  GoogleDriveHelpButton.Left := 0;
  GoogleDriveHelpButton.Top := ScaleY(150);
  GoogleDriveHelpButton.Width := ScaleX(170);
  GoogleDriveHelpButton.OnClick := @OpenGoogleDriveHelp;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if (GoogleDrivePage <> nil) and (PageID = GoogleDrivePage.ID) then
    Result := SkipGoogleDrivePrerequisite;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ContinueChoice: Integer;
begin
  Result := True;

  if (GoogleDrivePage = nil) or (CurPageID <> GoogleDrivePage.ID) then
    Exit;

  if GoogleDrivePage.SelectedValueIndex = 0 then
  begin
    Result := InstallGoogleDrive;
    Exit;
  end;

  ContinueChoice := MsgBox(
    'Script Manager dapat dipasang sekarang, tetapi folder proyek di Google Drive ' +
    'baru dapat digunakan setelah Google Drive for desktop dipasang dan login selesai.' + #13#10 + #13#10 +
    'Lanjutkan tanpa memasang Google Drive sekarang?',
    mbConfirmation,
    MB_YESNO
  );
  Result := ContinueChoice = IDYES;
end;
