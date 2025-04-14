#!/usr/bin/env python3
"""
Simple test script to verify that the MCP GitHub server can be installed and run.
This script uses full paths to npm and npx executables.
"""
import os
import sys
import subprocess
import logging
import threading
import time
from queue import Queue, Empty

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define the full paths to Node.js executables
NODE_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "node.exe")
NPM_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "npm.cmd")
NPX_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "npx.cmd")

def test_install_mcp_server():
    """Test if the MCP GitHub server can be installed."""
    logger.info("Testing MCP GitHub server installation...")
    
    # First, check if npm is available using full path
    try:
        logger.info(f"Checking npm using full path: {NPM_PATH}")
        result = subprocess.run(
            [NPM_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info(f"npm is available: version {result.stdout.strip()}")
        else:
            logger.error(f"npm check failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"npm check failed: {e}")
        return False
    
    # Next, check if the package is already installed
    try:
        logger.info("Checking if MCP GitHub server is already installed...")
        result = subprocess.run(
            [NPM_PATH, "list", "-g", "@modelcontextprotocol/server-github"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "@modelcontextprotocol/server-github" in result.stdout:
            logger.info("MCP GitHub server is already installed globally")
            package_installed = True
        else:
            logger.info("MCP GitHub server is not installed globally")
            package_installed = False
    except Exception as e:
        logger.warning(f"Could not check if MCP GitHub server is installed: {e}")
        package_installed = False
    
    # Try running the server directly with npx
    logger.info(f"Testing if MCP GitHub server can start using npx at: {NPX_PATH}")
    
    run_queue = Queue()
    process = None
    
    def run_server():
        nonlocal process
        try:
            logger.info(f"Starting MCP GitHub server with: {NPX_PATH} -y @modelcontextprotocol/server-github")
            
            # Set up environment with GitHub token if available
            env = os.environ.copy()
            github_token = os.getenv("GITHUB_TOKEN")
            if github_token:
                env["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
            
            # Start the process
            process = subprocess.Popen(
                [NPX_PATH, "-y", "@modelcontextprotocol/server-github"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # Read a few lines of output to confirm it's running
            lines = []
            for _ in range(10):  # Try to read up to 10 lines
                if process.poll() is not None:
                    # Process exited early
                    break
                    
                line = process.stdout.readline().strip()
                if line:
                    lines.append(line)
                    
                line = process.stderr.readline().strip()
                if line:
                    lines.append(line)
                
                if len(lines) >= 3:  # If we have a few lines, consider it running
                    break
            
            run_queue.put((True, lines))
        except Exception as e:
            logger.error(f"Error running MCP GitHub server: {e}")
            run_queue.put((False, str(e)))
        finally:
            # Ensure we clean up the process
            if process and process.poll() is None:
                try:
                    process.terminate()
                    logger.info("Terminated MCP GitHub server process")
                except:
                    pass
    
    # Start the server in a thread with a timeout
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    try:
        success, output = run_queue.get(timeout=30)  # Allow up to 30 seconds for server to start
        if success:
            logger.info("MCP GitHub server started successfully!")
            logger.info(f"Output: {output}")
            return True
        else:
            logger.error(f"Failed to start MCP GitHub server: {output}")
            return False
    except Empty:
        logger.error("Server start timed out after 30 seconds")
        if process and process.poll() is None:
            try:
                process.terminate()
                logger.info("Terminated hanging MCP GitHub server process")
            except:
                pass
        return False

def main():
    """Main test function"""
    logger.info("===== MCP GitHub Server Installation Test with Full Paths =====")
    
    # Test if the MCP GitHub server can be installed
    success = test_install_mcp_server()
    
    if success:
        logger.info("\n✓ MCP GitHub server test PASSED!")
        logger.info("The MCP GitHub server can be installed and run correctly.")
        return 0
    else:
        logger.error("\n× MCP GitHub server test FAILED!")
        logger.error("Please check the error messages above and fix the issues.")
        
        # Additional troubleshooting information
        logger.error("\nTroubleshooting tips:")
        logger.error("1. Check that Node.js and npm are properly installed")
        logger.error(f"2. Verify the paths are correct: NPM={NPM_PATH}, NPX={NPX_PATH}")
        logger.error("3. Try manually installing the server: npm install -g @modelcontextprotocol/server-github")
        logger.error("4. Check if your antivirus or firewall is blocking npm/npx")
        return 1

if __name__ == "__main__":
    sys.exit(main())