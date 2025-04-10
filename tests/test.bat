@echo off
:: Run specific tests or all tests for GitHub Documentation tool
:: Windows batch file version

SETLOCAL EnableDelayedExpansion

:: Colors for output (Windows console)
SET RED=[91m
SET GREEN=[92m
SET YELLOW=[93m
SET NC=[0m

echo %YELLOW%GitHub Documentation Testing Tool%NC%

:: Check python availability
python --version > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo %RED%Python could not be found. Please install Python.%NC%
    EXIT /B 1
)

:: Check for virtual environment
IF NOT EXIST "env\" (
    echo %YELLOW%Virtual environment not found. Creating one...%NC%
    python -m venv env
    
    :: Activate virtual environment
    CALL env\Scripts\activate
    
    :: Install dependencies
    echo %YELLOW%Installing dependencies...%NC%
    pip install -r ..\requirements.txt
) ELSE (
    :: Activate virtual environment
    CALL env\Scripts\activate
)

:: Function equivalent to run specific test
IF "%~1"=="" (
    :: Run all tests if no arguments provided
    echo %YELLOW%Running all tests...%NC%
    python run_tests.py
    SET RESULT=!ERRORLEVEL!
) ELSE (
    :: Run specific test based on first argument
    IF "%~1"=="github" (
        echo %YELLOW%Running github_token_test...%NC%
        python github_token_test.py
        SET RESULT=!ERRORLEVEL!
    ) ELSE IF "%~1"=="section" (
        echo %YELLOW%Running section_analyzer_test...%NC%
        python section_analyzer_test.py
        SET RESULT=!ERRORLEVEL!
    ) ELSE IF "%~1"=="claude" (
        echo %YELLOW%Running claude_test...%NC%
        python claude_test.py
        SET RESULT=!ERRORLEVEL!
    ) ELSE IF "%~1"=="mcp" (
        echo %YELLOW%Running mcp_client_test...%NC%
        python mcp_client_test.py
        SET RESULT=!ERRORLEVEL!
    ) ELSE IF "%~1"=="batch" (
        echo %YELLOW%Running batch_analyzer_test...%NC%
        python batch_analyzer_test.py --mock
        SET RESULT=!ERRORLEVEL!
    ) ELSE (
        echo %RED%Unknown test: %~1%NC%
        echo Available tests: github, section, claude, mcp, batch
        SET RESULT=1
    )
)

:: Deactivate virtual environment
deactivate

:: Return the result
IF !RESULT! EQU 0 (
    echo %GREEN%Tests completed successfully!%NC%
) ELSE (
    echo %RED%Tests failed with errors!%NC%
)

EXIT /B !RESULT!
