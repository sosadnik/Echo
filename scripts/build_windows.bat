@echo off
setlocal

py -m pip install -e .[build,local]
py -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --name Echo ^
  --windowed ^
  --paths src ^
  --add-data "src\echo_app\static;echo_app\static" ^
  src\echo_app\launcher.py

endlocal
