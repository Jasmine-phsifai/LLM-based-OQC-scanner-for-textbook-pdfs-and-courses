@echo off
chcp 65001 >nul 2>&1
setlocal

set "ENV_NAME=OCRLLM"
set "SCRIPT_DIR=%~dp0"
set "PACKAGE_DIR=%SCRIPT_DIR%OCRLLM"
set "PYTHON_EXE=D:\Anaconda\envs\OCRLLM\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo.
echo ============================================================
echo   OCRLLM GUI
echo ============================================================
echo.

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
    set "CONDA_BAT="
    for /f "delims=" %%I in ('where conda.bat 2^>nul') do (
        if not defined CONDA_BAT set "CONDA_BAT=%%I"
    )

    if not defined CONDA_BAT (
        where conda >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] The OCRLLM Python environment was not found.
            echo        Expected: D:\Anaconda\envs\OCRLLM\python.exe
            echo        Run legacy_app\setup_env.bat first.
            pause
            exit /b 1
        )
    )

    if defined CONDA_BAT (
        call "%CONDA_BAT%" activate %ENV_NAME%
    ) else (
        call conda activate %ENV_NAME%
    )
    if errorlevel 1 (
        echo [ERROR] Cannot activate conda environment %ENV_NAME%.
        echo        Run legacy_app\setup_env.bat first, or run conda init cmd.exe.
        pause
        exit /b 1
    )
)

cd /d "%SCRIPT_DIR%"
if not exist "%PACKAGE_DIR%\main.py" (
    echo [ERROR] GUI entrypoint was not found:
    echo        %PACKAGE_DIR%\main.py
    echo.
    echo Expected repo layout:
    echo        legacy_app\OCRLLM\main.py
    pause
    exit /b 1
)

"%PYTHON_EXE%" -m OCRLLM.main %*
if errorlevel 1 (
    echo.
    echo [ERROR] OCRLLM GUI failed to start.
    pause
    exit /b 1
)

endlocal
