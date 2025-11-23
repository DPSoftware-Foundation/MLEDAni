@echo off
title Copying DPGWidgets...

REM Copy folder from parent directory into current project
xcopy "..\DPGWidgets" ".\DPGWidgets" /E /I /Y >nul

title Building EXE...
pyinstaller --onefile --noconsole --icon=icon.ico ^
    --add-data "addicon.png;." ^
    --add-data "updateicon.png;." ^
    --add-data "DPGWidgets;DPGWidgets" ^
    main.py

title Cleaning up temporary files...

REM Remove copied folder after build
rmdir /S /Q ".\DPGWidgets"

REM Optional: delete pyinstaller build trash
rmdir /S /Q build
del /Q main.spec