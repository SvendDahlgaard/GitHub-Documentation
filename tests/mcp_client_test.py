#!/usr/bin/env python3
"""
Test script for GitHub MCP server integration with Claude CLI.
This tests both Claude CLI authentication and GitHub MCP server functionality.
"""
import os
import sys
import subprocess
import logging
import json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if the required environment variables and tools are available."""
    # Load environment variables from .env
    load_dotenv()
    logger.info("Loaded environment variables from .env file")
    
    # Check for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        logger.info("✓ GITHUB_TOKEN is set in the environment")
        # Set it as the variable expected by the GitHub MCP server
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
        logger.info("✓ Set GITHUB_PERSONAL_ACCESS_TOKEN from GITHUB_TOKEN")
    else:
        logger.error("× No GITHUB_TOKEN found in environment or .env file")
        logger.error("  Please set GITHUB_TOKEN in your .env file")
        return False
    
    # Check for Claude CLI
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"✓ Claude CLI is installed: {result.stdout.strip()}")
        else:
            logger.error(f"× Claude CLI test failed: {result.stderr}")
            return False
    except FileNotFoundError:
        logger.error("× Claude CLI not found in PATH")
        logger.error("  Please install it using: npm install -g @anthropic-ai/claude-cli")
        return False
    except Exception as e:
        logger.error(f"× Error checking Claude CLI: {e}")
        return False
    
    # Check if NPM is available for installing the GitHub MCP server
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"✓ NPM is installed: {result.stdout.strip()}")
        else:
            logger.warning(f"× NPM test failed: {result.stderr}")
            logger.warning("  You might need NPM to install the GitHub MCP server")
    except FileNotFoundError:
        logger.warning("× NPM not found in PATH")
        logger.warning("  You might need NPM to install the GitHub MCP server")
    
    # Check for GitHub MCP server package
    try:
        result = subprocess.run(
            ["npx", "-y", "@modelcontextprotocol/server-github", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"✓ GitHub MCP server is available via NPX")
        else:
            logger.warning("× GitHub MCP server not available via NPX")
            logger.warning("  You might need to install it: npm install -g @modelcontextprotocol/server-github")
    except Exception:
        logger.warning("× Error checking for GitHub MCP server")
        logger.warning("  You might need to install it: npm install -g @modelcontextprotocol/server-github")
    
    return True

def test_claude_auth():
    """Test if Claude CLI is properly authenticated."""
    logger.info("Testing Claude CLI authentication...")
    
    try:
        # Check if config directory exists
        config_path = os.path.expanduser("~/.config/anthropic/settings.json")
        if os.path.exists(config_path):
            logger.info(f"✓ Claude CLI config file found at {config_path}")
            
            # Try to read and parse without exposing the key
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                if 'apiKey' in config_data and config_data['apiKey'] and config_data['apiKey'] != "YOUR_ANTHROPIC_API_KEY":
                    logger.info("✓ API key found in config file")
                    
                    # Test with a non-interactive command that won't timeout
                    result = subprocess.run(
                        ["claude", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"✓ Claude CLI version check successful: {result.stdout.strip()}")
                        logger.info("✓ Claude CLI is configured with an API key")
                        return True
                    else:
                        logger.error(f"× Claude CLI version check failed: {result.stderr}")
                        return False
                else:
                    logger.error("× No valid API key found in config file")
                    logger.error("  Please update ~/.config/anthropic/settings.json with your API key")
                    return False
            except Exception as e:
                logger.error(f"× Error reading config file: {e}")
                return False
        else:
            logger.warning("× Claude CLI config file not found")
            logger.warning("  Please create ~/.config/anthropic/settings.json with your API key")
            
            # Try with a simple version check as fallback
            try:
                result = subprocess.run(
                    ["claude", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    logger.info(f"✓ Claude CLI is installed: {result.stdout.strip()}")
                    logger.warning("  Authentication might still fail for API calls")
                    # Return True to continue with tests even if we're not sure about auth
                    return True
                else:
                    logger.error(f"× Claude CLI version check failed: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"× Error checking Claude CLI: {e}")
                return False
    except Exception as e:
        logger.error(f"× Error testing Claude authentication: {e}")
        return False

def test_github_mcp_integration():
    """Test the GitHub MCP server integration with Claude."""
    logger.info("Testing GitHub MCP server integration...")
    
    # Test repository information
    test_owner = "SvendDahlgaard"
    test_repo = "GitHub-Documentation"
    
    try:
        # Create a temporary file with a prompt to use the GitHub MCP tool
        with open("test_github_mcp.txt", "w") as f:
            f.write(f"""
I need to use the GitHub MCP tool "search_repositories" with the following parameters:
```json
{{
  "query": "repo:{test_owner}/{test_repo}"
}}
```

Please execute this MCP tool and return only the raw JSON response without any additional text, explanation, or formatting.
            """)
        
        # Run Claude CLI with this file
        result = subprocess.run(
            ["claude", "send", "--print", "test_github_mcp.txt"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Check the output
        if result.returncode == 0:
            # Check if we got a proper JSON response
            json_match = re.search(r'```(?:json)?\n([\s\S]*?)\n```', result.stdout)
            json_str = None
            
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # Try to interpret the whole response as JSON
                json_str = result.stdout.strip()
            
            try:
                # Parse the JSON response
                response_data = json.loads(json_str)
                
                # Check if it's a valid GitHub repository response
                if "items" in response_data and len(response_data["items"]) > 0:
                    repo_name = response_data["items"][0].get("name")
                    logger.info(f"✓ Successfully got repository information: {repo_name}")
                    return True
                else:
                    logger.warning("? GitHub MCP server returned empty or unexpected response")
                    logger.warning(f"Response: {json_str[:200]}...")
            except json.JSONDecodeError:
                logger.error("× Failed to parse JSON from response")
                logger.error(f"Raw response: {result.stdout[:200]}...")
                
                if "Invalid API key" in result.stdout or "Please run /login" in result.stdout:
                    logger.error("× Claude CLI authentication failed - needs login")
                    logger.error("  Please run: claude login")
                elif "401 Unauthorized" in result.stdout or "Bad credentials" in result.stdout:
                    logger.error("× GitHub token is invalid or has insufficient permissions")
                    logger.error("  Check your GITHUB_TOKEN in the .env file")
                
                return False
        else:
            logger.error(f"× Claude CLI command failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"× Error testing GitHub MCP integration: {e}")
        return False
    finally:
        # Clean up test file
        if os.path.exists("test_github_mcp.txt"):
            os.remove("test_github_mcp.txt")

def setup_instructions():
    """Print setup instructions based on test results."""
    logger.info("\n===== GitHub MCP Setup Instructions =====")
    
    logger.info("1. Ensure Claude CLI is installed and authenticated:")
    logger.info("   npm install -g @anthropic-ai/claude-cli")
    logger.info("   For non-interactive environments (like WSL), set up API key authentication:")
    logger.info("   - Create directory: mkdir -p ~/.config/anthropic")
    logger.info("   - Create file: ~/.config/anthropic/settings.json with contents:")
    logger.info('   {"apiKey": "YOUR_ANTHROPIC_API_KEY"}')
    logger.info("   - Set permissions: chmod 600 ~/.config/anthropic/settings.json")
    logger.info("   - Or for interactive terminals: claude login")
    
    logger.info("\n2. Install the GitHub MCP server:")
    logger.info("   npm install -g @modelcontextprotocol/server-github")
    
    logger.info("\n3. Set your GitHub token:")
    logger.info("   Add GITHUB_TOKEN=your_token to your .env file")
    logger.info("   (This will be used as GITHUB_PERSONAL_ACCESS_TOKEN by the MCP server)")
    
    logger.info("\n4. Update your code to use the MCP GitHub client:")
    logger.info("   - Replace your existing mcp_github_client.py with the provided version")
    logger.info("   - Ensure it reads the GITHUB_TOKEN from your .env file")
    
    logger.info("\n5. Run your code with --skip-search flag initially:")
    logger.info("   python Repo-analyzer.py --owner user --repo repo --skip-search")
    
    logger.info("\nFor more details, see the GitHub MCP server documentation.")

if __name__ == "__main__":
    import re  # Import here for regex pattern matching
    
    logger.info("===== GitHub MCP Server Integration Test =====")
    
    # Check environment
    if not check_environment():
        logger.error("\nEnvironment setup incomplete. Please fix the issues above.")
        setup_instructions()
        sys.exit(1)
    
    # Test Claude authentication
    if not test_claude_auth():
        logger.error("\nClaude CLI authentication failed. Please run 'claude login'.")
        setup_instructions()
        sys.exit(1)
    
    # Test GitHub MCP integration
    if not test_github_mcp_integration():
        logger.error("\nGitHub MCP server integration test failed.")
        setup_instructions()
        sys.exit(1)
    
    logger.info("\n✓ All tests passed! Your GitHub MCP server integration is working correctly.")