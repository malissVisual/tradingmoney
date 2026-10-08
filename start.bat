@echo off
cd /d "%~dp0"
title EDGY Bot

if not exist "requirements.txt" goto notextracted
if not exist "bot\__main__.py" goto notextracted

rem Najdi Python: nejdriv spoustec py z python.org, jinak python napr. z Microsoft Storu.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto nopython

if exist ".venv\Scripts\python.exe" goto deps
echo  Pripravuji prostredi, chvili to potrva...
%PY% -m venv .venv
if errorlevel 1 goto failed

:deps
echo  Kontroluji knihovny, napoprve to muze trvat i 2 minuty...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto failed

if exist ".env" goto run
copy ".env.example" ".env" >nul
echo.
echo  Otviram soubor .env v Poznamkovem bloku.
echo  Za DISCORD_TOKEN= vloz token bota, uloz pres Ctrl+S a Poznamkovy blok zavri.
notepad ".env"

:run
echo.
echo  Spoustim bota. Okno nechej otevrene - kdyz ho zavres, bot se vypne.
echo.
".venv\Scripts\python.exe" -m bot
echo.
echo  Bot se zastavil. Pokud vyse vidis chybu, posli screenshot tohoto okna.
pause
exit /b 0

:notextracted
echo.
echo  start.bat nevidi ostatni soubory bota.
echo  Rozbal cely ZIP pres prave tlacitko - Extrahovat vse a spust start.bat
echo  ve slozce, kde jsou i slozky bot, texts a soubor requirements.txt.
pause
exit /b 1

:nopython
echo.
echo  Nenasel jsem Python 3.11 nebo novejsi - bud chybi, nebo je moc stary.
echo  Stahni ho z https://www.python.org/downloads/ a pri instalaci zaskrtni Add python.exe to PATH.
echo  Pak znovu spust start.bat.
start "" https://www.python.org/downloads/
pause
exit /b 1

:failed
echo.
echo  Neco se pokazilo. Posli screenshot tohoto okna.
pause
exit /b 1
