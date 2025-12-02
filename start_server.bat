@echo off
echo Starting Punjabi Chat Bot Server with Gemini 2.0 Flash...
echo.
echo Make sure you've set your GEMINI_API_KEY in the .env file!
echo.
uvicorn app.main:app --reload
pause
