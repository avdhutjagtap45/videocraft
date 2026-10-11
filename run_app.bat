@echo off
title AI Script-to-Video & Pixabay Asset Studio
echo ======================================================================
echo   Launching AI Script-to-Video & Pixabay Asset Studio
echo ======================================================================
echo.
echo Starting Streamlit app on http://localhost:8501 ...
echo (Keep this window open while using the application)
echo.
cd /d "%~dp0"
python -m streamlit run app.py
pause
