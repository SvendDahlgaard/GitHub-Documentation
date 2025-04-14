#!/usr/bin/env python3
"""
Simple test script to verify that the MCP GitHub server can be installed and run.
This script bypasses the complex client logic and directly tests the npm/npx functionality.
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

def find_npx_path():
    """Find the full path to npx executable."""
    # Check common installation locations
    common_paths = [
        os.path.join("C:", os.sep, "Program Files", "nodejs", "npx.cmd"),
        os.path.join("C:", os.sep, "Program Files (x86)", "nodejs", "npx.cmd"),
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm", "npx.cmd")
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            logger.info(f"Found npx at: {path}")
            return path
    
    # Try to find npx in PATH
    try:
        # Check if the command works directly
        result = subprocess.run(
            ["npx", "--version"], 
            capture_output=True, 
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            logger.info(f"npx is available directly: version {result.stdout.strip()}")
            return "npx"
    except Exception as e:
        logger.warning(f"npx is not directly available: {e}")
    
    logger.error("Could not find npx executable")
    return None

def test_install_mcp_server():
    """Test if the MCP GitHub server can be installed."""
    logger.info("Testing MCP GitHub server installation...")
    
    # First, check if npm is available
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=2
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
        result = subprocess.run(
            ["npm", "list", "-g", "@modelcontextprotocol/server-github"],
            capture_output=True,
            text=True,
            timeout=5
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
    
    # Find npx path
    npx_path = find_npx_path()
    if not npx_path:
        logger.error("Cannot continue without npx")
        return False
    
    # If not installed, try to install it
    if not package_installed:
        logger.info("Installing MCP GitHub server...")
        
        def run_install():
            try:
                # Try global installation first
                install_cmd = ["npm", "install", "-g", "@modelcontextprotocol/server-github"]
                logger.info(f"Running: {' '.join(install_cmd)}")
                
                result = subprocess.run(
                    install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    logger.info("Successfully installed MCP GitHub server globally")
                    return True
                else:
                    logger.error(f"Failed to install MCP GitHub server: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"Error during installation: {e}")
                return False
        
        # Run installation with a timeout
        install_queue = Queue()
        install_thread = threading.Thread(
            target=lambda: install_queue.put(run_install())
        )
        install_thread.daemon = True
        install_thread.start()
        
        try:
            success = install_queue.get(timeout=120)  # Allow up to 2 minutes for installation
            if not success:
                logger.error("Installation failed")
                return False
        except Empty:
            logger.error("Installation timed out after 2 minutes")
            return False
    
    # Test running the server (briefly)
    logger.info("Testing if MCP GitHub server can start...")
    
    run_queue = Queue()
    process = None
    
    def run_server():
        nonlocal process
        try:
            logger.info(f"Starting MCP GitHub server with: {npx_path} -y @modelcontextprotocol/server-github")
            
            # Set up environment with GitHub token if available
            env = os.environ.copy()
            github_token = os.getenv("GITHUB_TOKEN")
            if github_token:
                env["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
            
            # Start the process
            process = subprocess.Popen(
                [npx_path, "-y", "@modelcontextprotocol/server-github"],
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
        success, output = run_queue.get(timeout=20)  # Allow up to 20 seconds for server to start
        if success:
            logger.info("MCP GitHub server started successfully!")
            logger.info(f"Output: {output}")
            return True
        else:
            logger.error(f"Failed to start MCP GitHub server: {output}")
            return False
    except Empty:
        logger.error("Server start timed out after 20 seconds")
        if process and process.poll() is None:
            try:
                process.terminate()
                logger.info("Terminated hanging MCP GitHub server process")
            except:
                pass
        return False

def main():
    """Main test function"""
    logger.info("===== MCP GitHub Server Installation Test =====")
    
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
        logger.error("2. Try manually installing the server: npm install -g @modelcontextprotocol/server-github")
        logger.error("3. If you're using a proxy, make sure npm can access the internet")
        logger.error("4. Check if your antivirus or firewall is blocking npm/npx")
        return 1

if __name__ == "__main__":
    sys.exit(main())