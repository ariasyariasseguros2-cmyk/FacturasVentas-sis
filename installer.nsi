Unicode true

!define PRODUCT_NAME "FacturasVentas-SIS"
!define PRODUCT_VERSION "1.0.2"
!define PRODUCT_PUBLISHER "FacturasVentas-SIS"
!define PRODUCT_EXE "main.exe"

Name "${PRODUCT_NAME}"
Caption "Instalador de ${PRODUCT_NAME}"

OutFile "installer_release\FacturasVentas-SIS-Setup-${PRODUCT_VERSION}.exe"

InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"

InstallDirRegKey HKLM \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
    "InstallLocation"

RequestExecutionLevel admin

VIProductVersion "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "Aplicacion de gestion de facturas"

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles


; ============================================================
; INSTALACION
; ============================================================

Section "Aplicacion" SecApplication

    SetOutPath "$INSTDIR"

    ; Ejecutable generado por PyInstaller
    File "dist_release\main.exe"

    ; Accesos directos
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"

    CreateShortcut \
        "$DESKTOP\${PRODUCT_NAME}.lnk" \
        "$INSTDIR\${PRODUCT_EXE}"

    CreateShortcut \
        "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" \
        "$INSTDIR\${PRODUCT_EXE}"

    CreateShortcut \
        "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar.lnk" \
        "$INSTDIR\Uninstall.exe"

    ; Desinstalador
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Registro de Windows
    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "DisplayName" \
        "${PRODUCT_NAME}"

    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "DisplayVersion" \
        "${PRODUCT_VERSION}"

    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "Publisher" \
        "${PRODUCT_PUBLISHER}"

    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "InstallLocation" \
        "$INSTDIR"

    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "UninstallString" \
        "$INSTDIR\Uninstall.exe"

SectionEnd


; ============================================================
; DESINSTALACION
; ============================================================

Section "Uninstall"

    Delete "$DESKTOP\${PRODUCT_NAME}.lnk"

    Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar.lnk"

    RMDir "$SMPROGRAMS\${PRODUCT_NAME}"

    Delete "$INSTDIR\${PRODUCT_EXE}"
    Delete "$INSTDIR\Uninstall.exe"

    RMDir "$INSTDIR"

    DeleteRegKey HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

SectionEnd