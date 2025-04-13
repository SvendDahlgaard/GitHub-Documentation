#!/bin/bash
# Script to test and set up Claude CLI authentication in non-interactive environments like WSL

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== Claude CLI Authentication in Non-Interactive Environments =====${NC}"
echo

# Check if settings directory exists
echo -e "${YELLOW}Step 1: Checking for Claude CLI config directory...${NC}"
CONFIG_DIR="$HOME/.config/anthropic"

if [ -d "$CONFIG_DIR" ]; then
    echo -e "${GREEN}✓ Config directory found: $CONFIG_DIR${NC}"
else
    echo -e "${YELLOW}Creating config directory: $CONFIG_DIR${NC}"
    mkdir -p "$CONFIG_DIR"
    echo -e "${GREEN}✓ Config directory created${NC}"
fi

# Check if settings file exists
SETTINGS_FILE="$CONFIG_DIR/settings.json"
echo -e "${YELLOW}Step 2: Checking for Claude CLI settings file...${NC}"

if [ -f "$SETTINGS_FILE" ]; then
    echo -e "${GREEN}✓ Settings file found: $SETTINGS_FILE${NC}"
    
    # Check if it has a valid API key (without printing it)
    CONTAINS_PLACEHOLDER=$(grep -c "YOUR_ANTHROPIC_API_KEY" "$SETTINGS_FILE")
    if [ "$CONTAINS_PLACEHOLDER" -gt 0 ]; then
        echo -e "${RED}× Settings file contains a placeholder API key${NC}"
        echo -e "${YELLOW}Please update the settings file with your actual Anthropic API key:${NC}"
        echo -e "${YELLOW}$SETTINGS_FILE${NC}"
    else
        echo -e "${GREEN}✓ Settings file contains an API key${NC}"
    fi
else
    echo -e "${YELLOW}Creating settings file template: $SETTINGS_FILE${NC}"
    echo '{
  "apiKey": "YOUR_ANTHROPIC_API_KEY"
}' > "$SETTINGS_FILE"
    chmod 600 "$SETTINGS_FILE"
    echo -e "${GREEN}✓ Settings file template created${NC}"
    echo -e "${YELLOW}Please update the settings file with your actual Anthropic API key:${NC}"
    echo -e "${YELLOW}$SETTINGS_FILE${NC}"
fi

# Test Claude CLI
echo -e "${YELLOW}Step 3: Testing Claude CLI...${NC}"
CLAUDE_VERSION=$(claude --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Claude CLI is installed: $CLAUDE_VERSION${NC}"
else
    echo -e "${RED}× Claude CLI test failed: $CLAUDE_VERSION${NC}"
    echo -e "${YELLOW}Please install Claude CLI:${NC}"
    echo -e "${YELLOW}npm install -g @anthropic-ai/claude-cli${NC}"
fi

# Test MCP client
echo -e "${YELLOW}Step 4: Testing MCP GitHub client...${NC}"
python mcp_client_test.py

# Cleanup and completion message
echo -e "\n${BLUE}===== Setup Completion =====${NC}"
echo -e "${YELLOW}Setup steps completed.${NC}"
echo
echo -e "${YELLOW}If the tests failed, update your settings:${NC}"
echo "1. Edit your API key: $SETTINGS_FILE"
echo "2. Set permissions: chmod 600 $SETTINGS_FILE"
echo "3. Make sure your GITHUB_TOKEN is set in .env file"
echo
echo -e "${YELLOW}Run this script again to verify your setup.${NC}"