@echo off
REM The Data Mint - One-Click Training Launcher
REM Run this script to start the Gradio UI

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Check if gradio is installed
python -c "import gradio" 2>nul
if errorlevel 1 (
    echo Installing Gradio...
    pip install gradio
)

REM Run the launcher
echo Starting The Data Mint One-Click Launcher...
echo Open http://localhost:7860 in your browser
echo.

python -m launcher.gradio_launcher_app
