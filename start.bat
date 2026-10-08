@echo off
cd /d "%~dp0"
title EDGY Bot

where py >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python neni nainstalovany.
  echo  Stahni ho z https://www.python.org/downloads/ a pri instalaci zaskrtni "Add python.exe to PATH".
  echo  Pak znovu spust start.bat.
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  Pripravuji prostredi, chvili to potrva...
  py -3 -m venv .venv || goto :error
)
echo  Kontroluji knihovny...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo  Otviram soubor .env v Poznamkovem bloku.
  echo  Za DISCORD_TOKEN= vloz token bota, uloz (Ctrl+S) a Poznamkovy blok zavri.
  notepad ".env"
)

echo.
echo  Spoustim bota. Okno nechej otevrene - kdyz ho zavres, bot se vypne.
echo.
".venv\Scripts\python.exe" -m bot
echo.
echo  Bot se zastavil. Pokud vyse vidis chybu, posli screenshot tohoto okna.
pause
exit /b 0

:error
echo.
echo  Neco se pokazilo. Posli screenshot tohoto okna.
pause
exit /b 1
