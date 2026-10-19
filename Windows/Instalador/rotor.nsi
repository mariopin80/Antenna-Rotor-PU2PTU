; Template NSIS/Jinja usado pelo Pynsist 2.8.
; Instalacao por usuario, sem alterar o Python nem o PATH do computador.
Target amd64-unicode
Unicode true
ManifestDPIAware true
RequestExecutionLevel user
SetCompressor /SOLID lzma

!define PRODUCT_NAME "Rotor PU2PTU"
!define PRODUCT_VERSION "[[ib.version]]"
!define REG_APP "Software\MarioPin\RotorPU2PTU"
!define REG_UNINSTALL "Software\Microsoft\Windows\CurrentVersion\Uninstall\RotorPU2PTU"
!include "MUI2.nsh"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "[[ib.installer_name]]"
InstallDir "$LOCALAPPDATA\Programs\RotorPU2PTU"
InstallDirRegKey HKCU "${REG_APP}" "InstallDir"
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "1.2.1.0"
VIFileVersion "1.2.1.0"
VIAddVersionKey "ProductName" "Rotor PU2PTU"
VIAddVersionKey "FileDescription" "Instalador do Rotor PU2PTU"
VIAddVersionKey "CompanyName" "Mario Pin - PU2PTU"
VIAddVersionKey "LegalCopyright" "Mario Pin - PU2PTU"
VIAddVersionKey "FileVersion" "1.2.1.0"
VIAddVersionKey "ProductVersion" "1.2.1"

!define MUI_ICON "[[icon]]"
!define MUI_UNICON "[[icon]]"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Este assistente instala o Rotor PU2PTU 1.2.1 com mapa OpenStreetMap e apontamento por grid locator.$\r$\n$\r$\nO programa inclui o Python e as bibliotecas necessárias. A instalação funciona sem internet; o mapa usa internet ao carregar novas áreas.$\r$\n$\r$\nFeche o Rotor antes de atualizar."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o Rotor PU2PTU"
!define MUI_FINISHPAGE_RUN_FUNCTION RunRotor
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!define MUI_UNFINISHPAGE_TEXT "O programa foi removido. A configuração da estação e o cache do mapa foram preservados no seu perfil de usuário."
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "PortugueseBR"

Function .onInit
  SetShellVarContext current
  SetRegView 64
FunctionEnd

Section "Rotor PU2PTU (obrigatório)" SecApp
  SectionIn RO
  SetShellVarContext current
  SetRegView 64
  SetOverwrite on
  SetOutPath "$INSTDIR\pkgs"
  File /r "pkgs\*.*"

  [% for destination, group in grouped_files %]
  SetOutPath "[[destination]]"
    [% for file in group %]
  File "[[file]]"
    [% endfor %]
  [% endfor %]
  [% for dir, destination in ib.install_dirs %]
  SetOutPath "[[pjoin(destination, dir)]]"
  File /r "[[dir]]\*.*"
  [% endfor %]

  SetOutPath "$INSTDIR"
  CreateDirectory "$SMPROGRAMS\Rotor PU2PTU"
  [% for scname, sc in ib.shortcuts.items() %]
  CreateShortCut "$SMPROGRAMS\Rotor PU2PTU\[[scname]].lnk" "$INSTDIR\Python\Rotor_PU2PTU.exe" '[[sc['parameters']]]' "$INSTDIR\[[sc['icon']]]" 0 SW_SHOWNORMAL
  [% endfor %]
  WriteUninstaller "$INSTDIR\Desinstalar.exe"
  WriteRegStr HKCU "${REG_APP}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${REG_UNINSTALL}" "DisplayName" "Rotor PU2PTU"
  WriteRegStr HKCU "${REG_UNINSTALL}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${REG_UNINSTALL}" "Publisher" "Mario Pin - PU2PTU"
  WriteRegStr HKCU "${REG_UNINSTALL}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${REG_UNINSTALL}" "UninstallString" '$\"$INSTDIR\Desinstalar.exe$\"'
  WriteRegStr HKCU "${REG_UNINSTALL}" "QuietUninstallString" '$\"$INSTDIR\Desinstalar.exe$\" /S'
  WriteRegStr HKCU "${REG_UNINSTALL}" "DisplayIcon" "$INSTDIR\[[icon]]"
  WriteRegDWORD HKCU "${REG_UNINSTALL}" "NoModify" 1
  WriteRegDWORD HKCU "${REG_UNINSTALL}" "NoRepair" 1
SectionEnd

Section "Atalho na área de trabalho" SecDesktop
  SetOutPath "$INSTDIR"
  CreateShortCut "$DESKTOP\Rotor PU2PTU.lnk" "$INSTDIR\Python\Rotor_PU2PTU.exe" '$\"$INSTDIR\Rotor_PU2PTU.launch.pyw$\"' "$INSTDIR\[[icon]]" 0 SW_SHOWNORMAL
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp} "Programa completo, mapa, bibliotecas e atalhos no menu Iniciar. Inclui modo de simulação sem Arduino."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Cria o atalho Rotor PU2PTU na sua área de trabalho com o ícone do programa."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function RunRotor
  SetOutPath "$INSTDIR"
  Exec '$\"$INSTDIR\Python\Rotor_PU2PTU.exe$\" $\"$INSTDIR\Rotor_PU2PTU.launch.pyw$\"'
FunctionEnd

; Atualiza o Explorer depois de substituir os atalhos de uma versao anterior.
Function .onInstSuccess
  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
FunctionEnd

Function un.onInit
  SetShellVarContext current
  SetRegView 64
FunctionEnd

Section "Uninstall"
  Delete "$DESKTOP\Rotor PU2PTU.lnk"
  [% for scname in ib.shortcuts %]
  Delete "$SMPROGRAMS\Rotor PU2PTU\[[scname]].lnk"
  [% endfor %]
  RMDir "$SMPROGRAMS\Rotor PU2PTU"
  RMDir /r "$INSTDIR\pkgs"
  [% for file, destination in ib.install_files %]
  Delete "[[pjoin(destination, file)]]"
  [% endfor %]
  [% for dir, destination in ib.install_dirs %]
  RMDir /r "[[pjoin(destination, dir)]]"
  [% endfor %]
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${REG_UNINSTALL}"
  DeleteRegKey HKCU "${REG_APP}"
SectionEnd
