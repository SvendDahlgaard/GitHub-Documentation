#!/usr/bin/env python3
"""
Test MCP GitHub client for interacting with repositories.
"""
import os
import sys
from dotenv import load_dotenv
sys.path.append('..')  # Add parent directory to path
from mcp_github_client import MCPGitHubClient

def test_mcp_github_client():
    """Test MCP GitHub client's basic functionality."""
    # Load environment variables
    load_dotenv()
    
    print("Testing MCP GitHub client...")
    
    try:
        # Initialize client
        mcp_client = MCPGitHubClient()
        print("✓ Successfully initialized MCP GitHub client")
        
        # Default repository to test on
        owner = "SvendDahlgaard"
        repo = "GitHub-Documentation"
        
        # Try to search the repository
        print(f"\nSearching for repository: {owner}/{repo}")
        try:
            search_result = mcp_client.call_mcp_tool("search_repositories", {
                "query": f"repo:{owner}/{repo}"
            })
            
            if search_result and "items" in search_result and len(search_result["items"]) > 0:
                print(f"✓ Repository found: {search_result['items'][0]['full_name']}")
                print(f"✓ Default branch: {search_result['items'][0]['default_branch']}")
            else:
                print("× Repository not found in search results")
                return False
        except Exception as e:
            print(f"× Repository search failed: {e}")
            return False
        
        # Try to list some repository contents
        try:
            print(f"\nListing repository contents for {owner}/{repo}...")
            contents = mcp_client.list_repository_files(owner, repo, "")
            
            if contents and len(contents) > 0:
                print(f"✓ Successfully listed {len(contents)} items")
                print("\nSample files/directories:")
                for i, item in enumerate(contents[:3]):
                    print(f"  {i+1}. {item.get('name')} ({item.get('type')})")
            else:
                print("× No contents found")
                return False
        except Exception as e:
            print(f"× Failed to list repository contents: {e}")
            return False
        
        # Try code search if repository has Python files
        try:
            print(f"\nSearching for Python files in {owner}/{repo}...")
            search_results = mcp_client.search_code(owner, repo, "language:python")
            
            if search_results and len(search_results) > 0:
                print(f"✓ Found {len(search_results)} Python files")
                print("\nSample Python files:")
                for i, item in enumerate(search_results[:3]):
                    print(f"  {i+1}. {item.get('path')}")
                
                # Try searching for references to a file
                if search_results and len(search_results) > 0:
                    sample_file = search_results[0].get('path')
                    print(f"\nFinding files that reference {sample_file}...")
                    references = mcp_client.search_references(owner, repo, sample_file)
                    
                    if references:
                        print(f"✓ Found {len(references)} references to {sample_file}")
                        print("\nSample references:")
                        for i, ref in enumerate(list(references)[:3]):
                            print(f"  {i+1}. {ref}")
                    else:
                        print("No references found (this is not necessarily an error)")
            else:
                print("No Python files found (this is not necessarily an error)")
        except Exception as e:
            print(f"× Failed to perform code search: {e}")
            print("Code search may require additional setup or permissions")
        
        print("\n✓ MCP GitHub client is working!")
        return True
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mcp_github_client()
    
    if success:
        print("\nTest PASSED! MCP GitHub client is working correctly.")
        sys.exit(0)
    else:
        print("\nTest FAILED! Please check the error messages above.")
        sys.exit(1)