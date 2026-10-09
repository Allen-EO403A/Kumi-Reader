; Kumi Reader 安裝程式（Inno Setup 6）。
; Copyright (C) 2026 Allen <allen@umail.tw>，以 GPL-3.0-or-later 發布。
;
; 由 tools/build_installer.py 呼叫，不要直接編譯：
;   ISCC /DAppVersion=0.4.0 /DDotNetInstaller=<.NET 安裝檔路徑> installer/kumi-reader.iss
; 安裝內容為 tools/build_package.py 產生的 install/ 資料夾。

#ifndef AppVersion
  #error 請由 tools/build_installer.py 編譯（缺少 AppVersion）
#endif
#ifndef DotNetInstaller
  #error 請由 tools/build_installer.py 編譯（缺少 DotNetInstaller）
#endif

#define AppName "Kumi Reader"
#define AppDisplayName "Kumi 讀取程式"
#define RepoUrl "https://github.com/Allen-EO403A/Kumi-Reader"

[Setup]
AppId={{07DC2163-DF6B-45FB-9768-92D3A47852D6}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppDisplayName} {#AppVersion}
AppPublisher=Allen
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
AppCopyright=Copyright (C) 2026 Allen <allen@umail.tw>
; 讀取程式會在自己的資料夾寫入金鑰、安裝識別碼與本機結果，所以裝在使用者自己的資料夾（不需要系統管理員）
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Kumi-Reader
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\release
OutputBaseFilename=Kumi-Reader-Setup-v{#AppVersion}
UninstallDisplayName={#AppDisplayName}
UninstallDisplayIcon={app}\MFAAvalonia.exe
; 解除安裝程式（unins000.exe）放在 uninstall 子資料夾；安裝資料夾根目錄另有「解除安裝 Kumi 讀取程式」捷徑
UninstallFilesDir={app}\uninstall
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; 更新時關閉執行中的讀取程式
CloseApplications=yes

[Languages]
Name: "zhtw"; MessagesFile: "ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他："

[Files]
; 讀取程式本體（金鑰 .env、data/、debug/ 等執行時才產生的檔案不在這裡，更新時會保留）
Source: "..\install\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; .NET 10 Desktop Runtime：MFAAvalonia 需要，缺少時才安裝
Source: "{#DotNetInstaller}"; DestDir: "{tmp}"; DestName: "windowsdesktop-runtime-win-x64.exe"; Flags: deleteafterinstall; Check: NeedsDotNet

[Icons]
Name: "{autoprograms}\{#AppDisplayName}"; Filename: "{app}\MFAAvalonia.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppDisplayName}"; Filename: "{app}\MFAAvalonia.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{app}\解除安裝 {#AppDisplayName}"; Filename: "{uninstallexe}"; Comment: "解除安裝{#AppDisplayName}（金鑰與本機讀取結果會保留）"

[Run]
; .NET 安裝需要系統管理員權限：以 runas 啟動，會跳出 Windows 的權限確認
Filename: "{tmp}\windowsdesktop-runtime-win-x64.exe"; Parameters: "/install /quiet /norestart"; Verb: "runas"; Flags: shellexec waituntilterminated; StatusMsg: "正在安裝 .NET 10 Desktop Runtime…"; Check: NeedsDotNet
Filename: "{app}\MFAAvalonia.exe"; WorkingDir: "{app}"; Description: "開啟{#AppDisplayName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 執行時產生的 Python 快取。金鑰（.env）、data/、設定與紀錄檔由解除安裝時的詢問決定（見 [Code]）
Type: filesandordirs; Name: "{app}\agent\__pycache__"
Type: filesandordirs; Name: "{app}\agent\kumi_reader\__pycache__"

[Code]
{ 已安裝 .NET 10 的 Windows Desktop Runtime（x64）時不再安裝 }
function NeedsDotNet: Boolean;
var
  FindRec: TFindRec;
begin
  Result := True;
  if FindFirst(ExpandConstant('{commonpf64}\dotnet\shared\Microsoft.WindowsDesktop.App\10.*'), FindRec) then
  begin
    try
      repeat
        if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
          Result := False;
      until (not Result) or (not FindNext(FindRec));
    finally
      FindClose(FindRec);
    end;
  end;
end;

{ 移除完成視窗：勾選「同時刪除設定與資料」才刪除執行時產生的檔案（金鑰、本機讀取結果、設定、紀錄檔）。
  預設不勾（保留）；回傳是否勾選。 }
function AskDeleteData(const AppDir: String): Boolean;
var
  Form: TSetupForm;
  Intro, Note: TNewStaticText;
  DeleteData: TNewCheckBox;
  OkButton: TNewButton;
begin
  Form := CreateCustomForm(ScaleX(440), ScaleY(210), False, True);
  try
    Form.Caption := '解除安裝 {#AppDisplayName}';

    Intro := TNewStaticText.Create(Form);
    Intro.Parent := Form;
    Intro.Left := ScaleX(16);
    Intro.Top := ScaleY(16);
    Intro.Width := Form.ClientWidth - ScaleX(32);
    Intro.AutoSize := False;
    Intro.WordWrap := True;
    Intro.Height := ScaleY(36);
    Intro.Caption := '{#AppDisplayName}已移除。資料夾裡還留有執行時產生的設定與資料：' + #13#10 + AppDir;

    DeleteData := TNewCheckBox.Create(Form);
    DeleteData.Parent := Form;
    DeleteData.Left := ScaleX(16);
    DeleteData.Top := Intro.Top + Intro.Height + ScaleY(12);
    DeleteData.Width := Form.ClientWidth - ScaleX(32);
    DeleteData.Height := ScaleY(20);
    DeleteData.Caption := '同時刪除設定與資料（金鑰、本機還沒上傳的讀取結果、設定與紀錄檔）';
    DeleteData.Checked := False;

    Note := TNewStaticText.Create(Form);
    Note.Parent := Form;
    Note.Left := ScaleX(34);
    Note.Top := DeleteData.Top + DeleteData.Height + ScaleY(6);
    Note.Width := Form.ClientWidth - ScaleX(50);
    Note.AutoSize := False;
    Note.WordWrap := True;
    Note.Height := ScaleY(48);
    Note.Caption := '刪除後，重新安裝時要在網站產生新的金鑰（原本的金鑰已綁定這份安裝）。' +
      '不勾選會保留這些檔案，之後重新安裝可以直接沿用。';

    OkButton := TNewButton.Create(Form);
    OkButton.Parent := Form;
    OkButton.Caption := '完成';
    OkButton.Width := ScaleX(88);
    OkButton.Height := ScaleY(26);
    OkButton.Left := Form.ClientWidth - OkButton.Width - ScaleX(16);
    OkButton.Top := Form.ClientHeight - OkButton.Height - ScaleY(14);
    OkButton.ModalResult := mrOk;
    OkButton.Default := True;

    Form.ActiveControl := OkButton;
    Form.ShowModal;
    Result := DeleteData.Checked;
  finally
    Form.Free;
  end;
end;

{ 程式檔案移除後詢問要不要刪除留下的資料。靜默解除安裝時不詢問、一律保留；
  用安裝程式更新版本不會解除安裝，資料不受影響。 }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  AppDir := ExpandConstant('{app}');
  if UninstallSilent or not DirExists(AppDir) then
    Exit;
  if AskDeleteData(AppDir) then
  begin
    if not DelTree(AppDir, True, True, True) then
      MsgBox('有些檔案無法刪除（可能正在使用中），請稍後手動刪除：' + #13#10 + AppDir, mbError, MB_OK);
  end;
end;
