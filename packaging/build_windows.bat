@echo off
rem Builds the Windows installer. Needs Python 3.11+ and Inno Setup 6 installed.
rem Run from the repository root:  packaging\build_windows.bat
setlocal
cd /d "%~dp0\.."

python -m venv .build-venv || goto :error
call .build-venv\Scripts\activate.bat
python -m pip install --upgrade pip || goto :error
pip install -r requirements.txt -r requirements-dev.txt || goto :error

python -m pytest -q || goto :error
pyinstaller --noconfirm --clean packaging\CommunityManager.spec || goto :error

set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup not found. The app is built in dist\CommunityManager - zip that folder instead.
  goto :eof
)
%ISCC% packaging\installer.iss || goto :error
echo.
echo Done: dist\CommunityManager-Setup.exe
goto :eof

:error
echo Build failed.
exit /b 1
