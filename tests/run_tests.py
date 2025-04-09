#!/usr/bin/env python3
"""
Run all tests for the GitHub Documentation tool.
"""
import os
import sys
from github_token_test import test_github_token
from section_analyzer_test import test_section_analyzer
from claude_test import test_claude_analyzer
from mcp_client_test import test_mcp_github_client

def main():
    """Run all tests."""
    print("=" * 50)
    print("RUNNING ALL TESTS")
    print("=" * 50)
    
    # Test 1: GitHub Token
    print("\n\n1. TESTING GITHUB TOKEN\n" + "-" * 30)
    token_success = test_github_token()
    
    # Test 2: Section Analyzer
    print("\n\n2. TESTING SECTION ANALYZER\n" + "-" * 30)
    # Only proceed with section analyzer test if token test passed
    if token_success:
        # Default repository to test on
        default_owner = "SvendDahlgaard"
        default_repo = "GitHub-Documentation"
        
        # Allow command-line arguments to override defaults
        owner = sys.argv[1] if len(sys.argv) > 1 else default_owner
        repo = sys.argv[2] if len(sys.argv) > 2 else default_repo
        branch = sys.argv[3] if len(sys.argv) > 3 else None
        
        analyzer_success = test_section_analyzer(owner, repo, branch)
    else:
        print("Skipping section analyzer test due to GitHub token failure.")
        analyzer_success = False
    
    # Test 3: Claude Analyzer
    print("\n\n3. TESTING CLAUDE ANALYZER\n" + "-" * 30)
    claude_success = test_claude_analyzer()
    
    # Test 4: MCP GitHub Client
    print("\n\n4. TESTING MCP GITHUB CLIENT\n" + "-" * 30)
    mcp_success = test_mcp_github_client()
    
    # Summary
    print("\n\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"1. GitHub Token Test: {'PASSED' if token_success else 'FAILED'}")
    print(f"2. Section Analyzer Test: {'PASSED' if analyzer_success else 'FAILED'}")
    print(f"3. Claude Analyzer Test: {'PASSED' if claude_success else 'FAILED'}")
    print(f"4. MCP GitHub Client Test: {'PASSED' if mcp_success else 'FAILED'}")
    
    # Overall status
    if token_success and analyzer_success and claude_success and mcp_success:
        print("\nAll tests PASSED! Your setup is ready to use.")
        return 0
    else:
        # MCP failure isn't critical since it's an optional feature
        if not mcp_success and token_success and analyzer_success and claude_success:
            print("\nCore tests PASSED! MCP features may not be available but basic functionality works.")
            return 0
        else:
            print("\nSome core tests FAILED! Please address the issues before continuing.")
            return 1

if __name__ == "__main__":
    sys.exit(main())