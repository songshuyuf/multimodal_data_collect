; ──────────────────────────────────────────────────
; Inno Setup Script — AI 艺术诊疗多模态采集系统
; ──────────────────────────────────────────────────
; 用法: iscc installer.iss
; 输入: dist\AiArtTreat\ (PyInstaller onedir 输出)
; 输出: output\AiArtTreat_Setup_v0.7.0.exe

#define MyAppName      "AI 艺术诊疗多模态采集系统"
#define MyAppExeName   "AiArtTreat.exe"
#define MyAppPublisher "Westlake University TGAI Lab"
#define MyAppURL       "https://www.westlake.edu.cn"

; 从 version.py 中读取版本号（构建脚本会替换此处）
#define MyAppVersion   "0.7.0"

[Setup]
AppId={{B8F3A2E1-7C54-4D6B-9E82-1A3F5C7D9E0B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\AiArtTreat
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; 输出目录和文件名
OutputDir=output
OutputBaseFilename=AiArtTreat_Setup_v{#MyAppVersion}
; 图标
SetupIconFile=assets\logo.ico
UninstallDisplayIcon={app}\AiArtTreat.exe
; 压缩
Compression=lzma2/ultra64
SolidCompression=yes
; 权限
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; 安装包大小提示
DiskSpanning=no
; 安装向导
WizardStyle=modern
WizardSizePercent=120

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; 递归复制 PyInstaller 输出的全部内容
Source: "dist\AiArtTreat\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";   Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\logs\*"
Type: dirifempty; Name: "{app}\logs"
Type: files; Name: "{app}\config\.upload_cache\*"
Type: dirifempty; Name: "{app}\config\.upload_cache"
Type: files; Name: "{app}\data\sessions\*"
Type: dirifempty; Name: "{app}\data\sessions"
