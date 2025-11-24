@echo off
title Copying DPGWidgets...

REM Copy folder from parent directory into current project
xcopy "..\DPGWidgets" ".\DPGWidgets" /E /I /Y >nul

title Building EXE...
pyinstaller --onefile --noconsole --icon=icon.ico --strip ^
    --add-data "addicon.png;." ^
    --add-data "updateicon.png;." ^
    main.py

title Compressing with UPX...

REM Check EXE exists first (avoid error if build failed)
if exist "dist\main.exe" (
    echo Compressing main.exe with UPX...
    upx -9 -f -k "dist\main.exe"
) else (
    echo ERROR: main.exe not found! Skipping UPX compression.
)

title Cleaning up temporary files...

REM Remove copied folder after build
rmdir /S /Q ".\DPGWidgets"

REM Optional: delete PyInstaller build trash
rmdir /S /Q build
del /Q main.spec
