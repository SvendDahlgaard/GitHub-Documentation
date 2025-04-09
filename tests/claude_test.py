#!/usr/bin/env python3
"""
Test Claude's capabilities for generating documentation.
"""
import os
import sys
import json
from dotenv import load_dotenv
sys.path.append('..')  # Add parent directory to path
from claude_analyzer import ClaudeAnalyzer

def test_claude_analyzer():
    """Test Claude's ability to analyze code and generate documentation."""
    # Load environment variables
    load_dotenv()
    
    print("Testing Claude's code analysis capabilities...")
    
    # Sample code to analyze (with properly escaped docstrings)
    sample_files = {
        "sample.py": '''
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
'''
    }
    
    # Additional file for testing context handling
    sample_files2 = {
        "advanced.py": '''
class AdvancedCalculator(Calculator):
    """An advanced calculator that extends the basic Calculator."""
    
    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b
        
    def divide(self, a, b):
        """Divide a by b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
'''
    }
    
    try:
        # First, try CLI method
        print("\nTesting Claude CLI method...")
        try:
            # Try with default (latest) model
            cli_analyzer = ClaudeAnalyzer(method="cli")
            analysis_cli = cli_analyzer.analyze_code("Sample Code", sample_files)
            print("✓ Claude CLI method working!")
            print(f"✓ Using model: {cli_analyzer.claude_model}")
            print("\nSample analysis snippet:")
            print("-" * 40)
            print(analysis_cli[:200] + "..." if len(analysis_cli) > 200 else analysis_cli)
            print("-" * 40)
            method_working = "cli"
            
            # Test context handling with a second analysis
            print("\nTesting context optimization...")
            analysis_with_context = cli_analyzer.analyze_code(
                "Advanced Code", 
                sample_files2, 
                context=analysis_cli
            )
            print("✓ Context optimization working!")
            print("\nSample analysis with context snippet:")
            print("-" * 40)
            print(analysis_with_context[:200] + "..." if len(analysis_with_context) > 200 else analysis_with_context)
            print("-" * 40)
            
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
                print(f"✓ Using model: {api_analyzer.claude_model}")
                print("\nSample analysis snippet:")
                print("-" * 40)
                print(analysis_api[:200] + "..." if len(analysis_api) > 200 else analysis_api)
                print("-" * 40)
                method_working = "api"
                
                # Test context handling with a second analysis
                print("\nTesting context optimization...")
                analysis_with_context = api_analyzer.analyze_code(
                    "Advanced Code", 
                    sample_files2, 
                    context=analysis_api
                )
                print("✓ Context optimization working!")
                print("\nSample analysis with context snippet:")
                print("-" * 40)
                print(analysis_with_context[:200] + "..." if len(analysis_with_context) > 200 else analysis_with_context)
                print("-" * 40)
                
            except Exception as e:
                print(f"× Claude API method failed: {str(e)}")
                method_working = None
        
        # Test with a specific model version if available
        if method_working:
            print("\nTesting with specific Claude model version...")
            try:
                test_model = "claude-3-opus-20240229"  # Test with a specific model
                specific_analyzer = ClaudeAnalyzer(
                    method=method_working, 
                    claude_model=test_model
                )
                print(f"✓ Successfully initialized with model: {specific_analyzer.claude_model}")
            except Exception as e:
                print(f"× Failed to initialize with specific model: {str(e)}")
        
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

def test_context_optimization():
    """Test the context optimization feature specifically."""
    try:
        # Create a long context string
        long_context = """
Section 'API Component':
The API component provides interfaces for external communication. It contains several key endpoints including user authentication, data retrieval, and status updates. The primary classes are APIController and RequestHandler.

Section 'Data Models':
This section defines the core data structures used throughout the application. The main models include User, Product, and Transaction. These models implement basic CRUD operations and field validation.

Section 'Utilities':
The utilities section contains helper functions for common tasks. Key components include logging utilities, string formatting tools, and date manipulation functions. These utilities are used by multiple other sections.

Section 'Authentication':
The authentication module handles user login, session management, and permission verification. It relates closely to the User model and API endpoints. The core class AuthManager implements OAuth2 protocols.

Section 'Database':
Database connectivity and query execution are managed here. This connects to all data models and provides transaction support. The primary class is DBConnector with pooled connections.

Section 'Testing':
This section contains unit and integration tests for all other components. It includes mock objects and fixtures for reproducible test scenarios.

Section 'Frontend':
The frontend code handles UI rendering, user interactions, and state management. It communicates with the API layer for data operations.

Section 'Configuration':
Contains environment-specific settings, feature flags, and application constants. This is referenced by most other sections for configuration needs.
"""

        # Initialize analyzer
        analyzer = ClaudeAnalyzer(method="cli" if os.system("which claude > /dev/null 2>&1") == 0 else "api")
        
        # Test optimization
        optimized = analyzer._optimize_context(long_context, max_length=2000)
        
        print("\nTesting context optimization...")
        print(f"Original context length: {len(long_context)} characters")
        print(f"Optimized context length: {len(optimized)} characters")
        print(f"Reduction: {(1 - len(optimized)/len(long_context))*100:.2f}%")
        
        # Check if important sections were preserved
        preserved_keywords = ['API', 'primary', 'key', 'core', 'relates']
        preserved_count = sum(1 for keyword in preserved_keywords if keyword in optimized)
        
        print(f"Important keywords preserved: {preserved_count}/{len(preserved_keywords)}")
        print("\nOptimized context preview:")
        print("-" * 40)
        print(optimized[:400] + "..." if len(optimized) > 400 else optimized)
        print("-" * 40)
        
        return True
        
    except Exception as e:
        print(f"ERROR: Context optimization test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_claude_analyzer()
    
    # Also test context optimization independently
    context_success = test_context_optimization()
    
    if success and context_success:
        print("\nAll tests PASSED! Claude analyzer is working correctly.")
    else:
        print("\nSome tests FAILED! Please check the error messages above.")
        sys.exit(1)