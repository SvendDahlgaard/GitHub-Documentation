#!/usr/bin/env python3
"""
Helper script to install the MCP GitHub server module.
This helps ensure the server module is correctly installed before trying to use it.
"""
import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define full paths to Node.js executables for Windows
NODE_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "node.exe")
NPM_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "npm.cmd")
NPX_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "npx.cmd")

def main():
    """Main function to install MCP GitHub server."""
    logger.info("Installing MCP GitHub server...")

    # Check if npm is available
    npm_cmd = NPM_PATH if os.path.exists(NPM_PATH) else "npm"
    
    try:
        logger.info(f"Checking npm using: {npm_cmd}")
        result = subprocess.run(
            [npm_cmd, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"npm is available, version: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"npm check failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error(f"npm not found at {npm_cmd}")
        logger.error("Please ensure npm is properly installed and in your PATH.")
        sys.exit(1)
    
    # Install the MCP GitHub server module globally
    try:
        logger.info("Installing @modelcontextprotocol/server-github globally...")
        result = subprocess.run(
            [npm_cmd, "install", "-g", "@modelcontextprotocol/server-github"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info("MCP GitHub server installed successfully!")
        logger.info(f"Output: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Installation failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error("Failed to run npm install command")
        sys.exit(1)
    
    # Verify the installation by checking if the package is now available
    try:
        logger.info("Verifying installation...")
        result = subprocess.run(
            [npm_cmd, "list", "-g", "@modelcontextprotocol/server-github"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if "@modelcontextprotocol/server-github" in result.stdout:
            logger.info("Verification successful! MCP GitHub server is installed.")
            logger.info(f"Package info: {result.stdout.strip()}")
        else:
            logger.warning("Package not found in global modules after installation.")
            logger.warning("Installation may have failed or package may be installed elsewhere.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Verification failed: {e}")
        logger.error(f"stderr: {e.stderr}")
    
    logger.info("Installation process completed.")
    
    # Let the user know what to do next
    logger.info("\nNext steps:")
    logger.info("1. Try running the test script:")
    logger.info("   python tests/test_mcp_server_fullpath.py")
    logger.info("2. If that works, try the main MCP connection test:")
    logger.info("   python tests/test_mcp_connection.py")
    logger.info("3. Finally, use the MCP client in your code:")
    logger.info("   python Repo-analyzer.py --owner <username> --repo <repository-name> --client-type mcp")

if __name__ == "__main__":
    main()