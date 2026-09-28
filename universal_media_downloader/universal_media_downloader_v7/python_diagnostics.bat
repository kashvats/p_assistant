@echo off
echo ===== Python diagnostics =====
echo.
echo PATH:
echo %PATH%
echo.
echo where python:
where.exe python 2>nul
echo.
echo where py:
where.exe py 2>nul
echo.
echo python test:
python -c "import sys; print(sys.executable); print(sys.version)" 2>nul
echo.
echo py test:
py -3 -c "import sys; print(sys.executable); print(sys.version)" 2>nul
echo.
pause
