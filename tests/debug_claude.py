#!/usr/bin/env python3
"""
Debug script for Claude analyzer functionality.
Provides detailed logging to help identify issues.
"""
import os
import sys
import subprocess
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Add parent directory to path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
logger.info(f"Added parent directory to path: {parent_dir}")
logger.info(f"Current sys.path: {sys.path}")

# Load environment variables
load_dotenv()
logger.info("Loaded environment variables from .env file")

def check_environment():
    """Check environment setup for Claude testing."""
    logger.info("Checking environment...")
    
    # Check Python version
    logger.info(f"Python version: {sys.version}")
    
    # Check for Claude CLI
    try:
        claude_result = subprocess.run(["which", "claude"], capture_output=True, text=True)
        if claude_result.returncode == 0:
            claude_path = claude_result.stdout.strip()
            logger.info(f"Found Claude CLI at: {claude_path}")
            
            # Check Claude version
            version_result = subprocess.run([claude_path, "--version"], capture_output=True, text=True)
            if version_result.returncode == 0:
                logger.info(f"Claude CLI version: {version_result.stdout.strip()}")
            else:
                logger.warning(f"Could not get Claude CLI version: {version_result.stderr}")
        else:
            logger.warning("Claude CLI not found in PATH")
            
            # Try to find it in common locations
            common_paths = [
                os.path.expanduser("~/.local/bin/claude"),
                "/usr/local/bin/claude",
                "/usr/bin/claude"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    logger.info(f"Found Claude CLI at: {path}")
                    break
            else:
                logger.error("Claude CLI not found in common locations")
    except Exception as e:
        logger.error(f"Error checking for Claude CLI: {e}")
    
    # Check for Claude API key
    api_key = os.getenv("CLAUDE_API_KEY")
    if api_key:
        logger.info("CLAUDE_API_KEY environment variable is set")
    else:
        logger.warning("CLAUDE_API_KEY environment variable is not set")
    
    # Check for other required modules
    try:
        import requests
        logger.info("requests module is available")
    except ImportError:
        logger.error("requests module is not available - required for API mode")
    
    # Print all environment variables (excluding API keys and tokens)
    safe_vars = {}
    for key, value in os.environ.items():
        if "key" in key.lower() or "token" in key.lower() or "password" in key.lower() or "secret" in key.lower():
            safe_vars[key] = "********"
        else:
            safe_vars[key] = value
    
    logger.debug(f"Environment variables: {safe_vars}")

def test_simple_claude_command():
    """Test a very basic Claude CLI command."""
    logger.info("Testing simple Claude CLI command...")
    
    try:
        # Use a simple command that should work
        test_cmd = ["claude", "send", "--help"]
        logger.info(f"Executing command: {' '.join(test_cmd)}")
        
        result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("Claude CLI basic command successful")
            logger.debug(f"Output (first 200 chars): {result.stdout[:200]}...")
        else:
            logger.error(f"Claude CLI basic command failed with code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
    except Exception as e:
        logger.error(f"Error testing Claude CLI: {e}")

def test_claude_echo():
    """Test Claude CLI with a simple echo command."""
    logger.info("Testing Claude CLI with a simple message...")
    
    try:
        with open("test_prompt.txt", "w") as f:
            f.write("Say 'Hello, testing Claude CLI!'")
        
        test_cmd = ["claude", "send", "test_prompt.txt"]
        logger.info(f"Executing command: {' '.join(test_cmd)}")
        
        result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info("Claude CLI echo test successful")
            logger.info(f"Response: {result.stdout}")
        else:
            logger.error(f"Claude CLI echo test failed with code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
    except Exception as e:
        logger.error(f"Error testing Claude echo: {e}")
    finally:
        # Clean up
        if os.path.exists("test_prompt.txt"):
            os.remove("test_prompt.txt")

def test_batch_analyzer():
    """Test BatchClaudeAnalyzer functionality."""
    logger.info("Testing BatchClaudeAnalyzer...")
    
    try:
        from batch_claude_analyzer import BatchClaudeAnalyzer
        logger.info("Successfully imported BatchClaudeAnalyzer")
        
        # Check if we have an API key for testing
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            logger.error("No CLAUDE_API_KEY found - cannot test BatchClaudeAnalyzer")
            return
            
        # Try to initialize with mock mode
        mock_analyzer = BatchClaudeAnalyzer(
            api_key=api_key,
            claude_model="claude-3-5-haiku-20241022"
        )
        logger.info(f"Successfully initialized BatchClaudeAnalyzer with model: {mock_analyzer.claude_model}")
        
    except ImportError as e:
        logger.error(f"Failed to import BatchClaudeAnalyzer: {e}")
    except Exception as e:
        logger.error(f"Error initializing BatchClaudeAnalyzer: {e}")

def try_import_claude_analyzer():
    """Try to import the ClaudeAnalyzer class."""
    logger.info("Trying to import ClaudeAnalyzer...")
    
    try:
        from claude_analyzer import ClaudeAnalyzer
        logger.info("Successfully imported ClaudeAnalyzer")
        
        # Check if we can create an instance
        try:
            analyzer = ClaudeAnalyzer(method="cli")
            logger.info("Successfully created ClaudeAnalyzer instance with CLI method")
            
            # Check the executable path
            logger.info(f"Claude executable path: {analyzer.claude_executable}")
            
            # Check if the executable exists
            if os.path.exists(analyzer.claude_executable):
                logger.info(f"Claude executable exists at {analyzer.claude_executable}")
            elif "/" not in analyzer.claude_executable and "\\" not in analyzer.claude_executable:
                logger.info("Claude executable is expected to be in PATH")
            else:
                logger.warning(f"Claude executable not found at {analyzer.claude_executable}")
                
        except Exception as e:
            logger.error(f"Error creating ClaudeAnalyzer instance: {e}")
    except ImportError as e:
        logger.error(f"Failed to import ClaudeAnalyzer: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during import: {e}")

if __name__ == "__main__":
    logger.info("Starting Claude debug script")
    
    check_environment()
    
    test_simple_claude_command()
    
    test_claude_echo()
    
    try_import_claude_analyzer()
    
    test_batch_analyzer()
    
    logger.info("Debug script completed")