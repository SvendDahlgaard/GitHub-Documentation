#!/usr/bin/env python3
"""
Test script specifically for Claude Code CLI.
"""
import os
import sys
import subprocess
import tempfile
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Add parent directory to path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

def test_claude_code_directly():
    """Test Claude Code CLI directly with simple commands."""
    print("Testing Claude Code CLI directly...")
    
    # Create a simple test prompt
    with tempfile.NamedTemporaryFile(suffix='.txt', mode='w+', delete=False) as temp_file:
        temp_file.write("What is Python? Give a brief explanation in one paragraph.")
        temp_file_path = temp_file.name
    
    try:
        # First, test with Claude's direct mode which should work
        print("\nTesting Claude CLI direct mode (prompt as argument)...")
        result = subprocess.run(
            ["claude", "-p", "Say hello"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print("✓ Claude direct mode works!")
            print(f"Output: {result.stdout.strip()[:100]}...")
        else:
            print(f"× Claude direct mode failed: {result.stderr}")
            
        # Test with file input using -p flag
        print("\nTesting Claude Code with file input using -p flag...")
        result = subprocess.run(
            ["claude", "-p", temp_file_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print("✓ Claude Code with file input works!")
            print(f"Output: {result.stdout.strip()[:100]}...")
        else:
            print(f"× Claude Code with file input failed: {result.stderr}")
        
        # Try with send command for compatibility with older Claude CLI
        print("\nTesting with 'claude send' command...")
        result = subprocess.run(
            ["claude", "send", temp_file_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print("✓ 'claude send' command works!")
            print(f"Output: {result.stdout.strip()[:100]}...")
        else:
            print(f"× 'claude send' command failed: {result.stderr}")
            
        return True
        
    except subprocess.TimeoutExpired:
        print("ERROR: Claude command timed out")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def test_with_claude_analyzer():
    """Test using ClaudeAnalyzer with Claude Code."""
    try:
        from claude_analyzer import ClaudeAnalyzer
        
        print("\nTesting with ClaudeAnalyzer...")
        analyzer = ClaudeAnalyzer(method="cli")
        
        # Check if we detected Claude Code correctly
        if hasattr(analyzer, 'is_claude_code'):
            print(f"Detected Claude Code: {analyzer.is_claude_code}")
        else:
            print("Could not detect if using Claude Code")
        
        # Test a simple analysis
        sample_files = {
            "hello.py": """
def hello_world():
    \"\"\"Print a hello world message.\"\"\"
    print("Hello, World!")
"""
        }
        
        print("\nAnalyzing sample code...")
        result = analyzer.analyze_code("Hello World Sample", sample_files)
        
        if result and not result.startswith("Error:"):
            print("✓ Successfully analyzed sample code!")
            print(f"Result preview: {result[:100]}...")
            return True
        else:
            print(f"× Analysis failed: {result}")
            return False
        
    except Exception as e:
        print(f"ERROR: Failed to test with ClaudeAnalyzer: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Claude Code CLI Test ===")
    
    # Test direct CLI usage
    direct_success = test_claude_code_directly()
    
    # Test with ClaudeAnalyzer
    analyzer_success = test_with_claude_analyzer()
    
    if direct_success and analyzer_success:
        print("\n✓ All Claude Code tests PASSED!")
        sys.exit(0)
    else:
        print("\n× Some Claude Code tests FAILED!")
        sys.exit(1)