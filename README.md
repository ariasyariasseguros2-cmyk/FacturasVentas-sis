# FacturasVentas-SIS

## Compilar la aplicacion

```powershell
pyinstaller --clean --noconfirm --workpath build_release --distpath dist_release main.spec
```

El ejecutable se genera como `dist_release\main.exe`.

## Crear el instalador NSIS

Instala NSIS y ejecuta:

```powershell
makensis installer.nsi
```

El instalador se genera como `dist_release\FacturasVentas-SIS-Setup.exe` y registra la aplicacion instalada como `main.exe`.