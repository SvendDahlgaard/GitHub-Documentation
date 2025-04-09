#!/bin/bash
# Run specific tests or all tests

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check python availability
if ! command -v python3 &> /dev/null
then
    echo -e "${RED}Python 3 could not be found. Please install Python 3.${NC}"
    exit 1
fi

# Check for virtual environment
if [ ! -d "env" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv env
    
    # Activate virtual environment
    source env/bin/activate
    
    # Install dependencies
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
else
    # Activate virtual environment
    source env/bin/activate
fi

# Function to run specific test
run_test() {
    local test_name=$1
    echo -e "${YELLOW}Running $test_name test...${NC}"
    
    if python3 ${test_name}.py "$@"; then
        echo -e "${GREEN}$test_name test PASSED${NC}"
        return 0
    else
        echo -e "${RED}$test_name test FAILED${NC}"
        return 1
    fi
}

# Check for arguments
if [ $# -eq 0 ]; then
    # Run all tests if no arguments provided
    echo -e "${YELLOW}Running all tests...${NC}"
    python3 run_tests.py
else
    # Run specific test based on first argument
    case $1 in
        "github")
            run_test github_token_test
            ;;
        "section")
            run_test section_analyzer_test
            ;;
        "claude")
            run_test claude_test
            ;;
        "mcp")
            run_test mcp_client_test
            ;;
        *)
            echo -e "${RED}Unknown test: $1${NC}"
            echo "Available tests: github, section, claude, mcp"
            exit 1
            ;;
    esac
fi

# Deactivate virtual environment
deactivate