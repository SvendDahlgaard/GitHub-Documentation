#!/usr/bin/env python3
"""
Test Claude's capabilities for generating documentation.
"""
import os
import sys
import json
from dotenv import load_dotenv
from claude_analyzer import ClaudeAnalyzer

def test_claude_analyzer():
    """Test Claude's ability to analyze code and generate documentation."""
    # Load environment variables
    load_dotenv()
    
    print("Testing Claude's code analysis capabilities...")
    
    # Sample code to analyze
    sample_files = {
        "sample.py": """
def hello_world():
    """Print a hello world message."""
    print("Hello, World!")
    
class Calculator:
    """A simple calculator class."""
    
    def add(self, a, b):
        """Add two numbers."""
        return a + b
        
    def subtract(self, a, b):
        """Subtract b from a."""
        return a - b
"""
    }
    
    try:
        # First, try CLI method
        print("\nTesting Claude CLI method...")
        try:
            cli_analyzer = ClaudeAnalyzer(method="cli")
            analysis_cli = cli_analyzer.analyze_code("Sample Code", sample_files)
            print("✓ Claude CLI method working!")
            print("\nSample analysis snippet:")
            print("-" * 40)
            print(analysis_cli[:200] + "..." if len(analysis_cli) > 200 else analysis_cli)
            print("-" * 40)
            method_working = "cli"
        except Exception as e:
            print(f"× Claude CLI method failed: {str(e)}")
            method_working = None
        
        # Then try API method if CLI failed
        if method_working is None:
            print("\nFalling back to Claude API method...")
            try:
                api_analyzer = ClaudeAnalyzer(method="api")
                analysis_api = api_analyzer.analyze_code("Sample Code", sample_files)
                print("✓ Claude API method working!")
                print("\nSample analysis snippet:")
                print("-" * 40)
                print(analysis_api[:200] + "..." if len(analysis_api) > 200 else analysis_api)
                print("-" * 40)
                method_working = "api"
            except Exception as e:
                print(f"× Claude API method failed: {str(e)}")
                method_working = None
        
        if method_working:
            print(f"\n✓ Claude analyzer is working using the {method_working.upper()} method")
            return True
        else:
            print("\n× Both Claude analysis methods failed")
            print("Make sure you have either:")
            print("1. Set up Claude CLI and provided the correct executable path")
            print("2. Set CLAUDE_API_KEY in your .env file")
            return False
            
    except Exception as e:
        print(f"ERROR: Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_claude_analyzer()
    
    if success:
        print("\nTest PASSED! Claude analyzer is working correctly.")
    else:
        print("\nTest FAILED! Please check the error messages above.")
        sys.exit(1)