@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================================
echo   Google Flow Educational Video Studio — Local Testbench (gemini_local_ui)
echo ============================================================================
if "%~1"=="" (
    echo Running default multi-scene 720p H.264 + Voiceover synthesis...
    python flow_testbench_runner.py
) else (
    echo Generating custom topic: %*
    python flow_testbench_runner.py %*
)
echo.
echo Opening interactive HTML5 player (index.html)...
start "" "%~dp0index.html"
