#!/usr/bin/env python3
"""
Test script to verify the MCP GitHub server connection and functionality.
This script tests:
1. Initializing the MCP GitHub client
2. Basic GitHub operations through MCP
3. Code search functionality
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add parent directory to path if needed
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def test_mcp_github_client():
    """Test the MCP GitHub client connection and basic functionality."""
    try:
        # Import the client (this also verifies the file can be imported)
        from mcp_github_client import MCPGitHubClient
        logger.info("✓ Successfully imported MCPGitHubClient")
        
        # Check if GitHub token is available
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            logger.error("× No GITHUB_TOKEN found in environment")
            logger.error("  Please set your GitHub token in the .env file")
            return False
        logger.info("✓ Found GITHUB_TOKEN in environment")
        
        # Initialize the client
        logger.info("Initializing MCP GitHub client...")
        client = MCPGitHubClient(use_cache=False)
        logger.info("✓ Successfully initialized MCP GitHub client")
        
        # Test repository for analysis (default to user's repo)
        test_owner = "SvendDahlgaard"
        test_repo = "GitHub-Documentation"
        
        # Test getting repository stats
        logger.info(f"Getting repository stats for {test_owner}/{test_repo}...")
        try:
            repo_stats = client.get_repository_stats(test_owner, test_repo)
            if repo_stats:
                logger.info(f"✓ Successfully retrieved repository stats")
                logger.info(f"Repository: {repo_stats.get('name')}")
                logger.info(f"Default branch: {repo_stats.get('default_branch')}")
                logger.info(f"Language: {repo_stats.get('language')}")
            else:
                logger.warning(f"× Could not retrieve repository stats (empty response)")
        except Exception as e:
            logger.error(f"× Error getting repository stats: {e}")
            return False
        
        # Test listing repository files
        logger.info(f"Listing files in repository {test_owner}/{test_repo}...")
        try:
            files = client._list_repository_files(test_owner, test_repo, "")
            logger.info(f"✓ Found {len(files)} files/directories in root")
            
            # Print a few files for verification
            if files:
                logger.info("Sample files/directories:")
                for i, file in enumerate(files[:5]):
                    logger.info(f"  {i+1}. {file.get('name')} ({file.get('type')})")
        except Exception as e:
            logger.error(f"× Error listing repository files: {e}")
            return False
        
        # Test getting file content
        if files:
            # Find a Python file to test
            python_files = [f for f in files if f.get('name', '').endswith('.py') and f.get('type') == 'file']
            if python_files:
                test_file = python_files[0]['path']
            else:
                # Fallback to README.md
                readme_files = [f for f in files if f.get('name') == 'README.md' and f.get('type') == 'file']
                if readme_files:
                    test_file = readme_files[0]['path']
                else:
                    # Just take the first file
                    test_file = next((f['path'] for f in files if f.get('type') == 'file'), None)
            
            if test_file:
                logger.info(f"Getting content of file: {test_file}")
                try:
                    content = client._get_file_content(test_owner, test_repo, test_file)
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                    logger.info(f"✓ Successfully retrieved file content: {content_preview}")
                except Exception as e:
                    logger.error(f"× Error getting file content: {e}")
                    return False
            else:
                logger.warning("No suitable files found for content test")
        
        # Test code search functionality
        logger.info("Testing code search functionality...")
        try:
            search_query = "import"  # Simple query that should find results in most repos
            search_results = client.search_code(test_owner, test_repo, search_query)
            
            if search_results:
                logger.info(f"✓ Found {len(search_results)} code search results for '{search_query}'")
                
                # Show a few results
                logger.info("Sample search results:")
                for i, result in enumerate(search_results[:3]):
                    logger.info(f"  {i+1}. {result.get('path')}")
                
                # Test references search if we have search results
                if len(search_results) > 0:
                    reference_file = search_results[0].get('path')
                    logger.info(f"Testing references search for file: {reference_file}")
                    
                    try:
                        references = client.search_references(test_owner, test_repo, reference_file)
                        logger.info(f"✓ Found {len(references)} references to {reference_file}")
                        
                        # Show some references
                        if references:
                            logger.info("Sample references:")
                            for i, ref in enumerate(list(references)[:3]):
                                logger.info(f"  {i+1}. {ref}")
                    except Exception as e:
                        logger.error(f"× Error searching for references: {e}")
            else:
                logger.warning(f"× No search results found for '{search_query}'")
                
        except Exception as e:
            logger.error(f"× Error performing code search: {e}")
            return False
        
        # Clean up (important to terminate the server process)
        logger.info("Test completed. Cleaning up...")
        del client
        
        logger.info("✓ All MCP GitHub client tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"× Error in MCP GitHub client test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    logger.info("===== MCP GitHub Client Connection Test =====")
    
    # Run the MCP GitHub client test
    success = test_mcp_github_client()
    
    if success:
        logger.info("\n✓ MCP GitHub client test PASSED!")
        logger.info("The MCP GitHub integration is working correctly.")
        return 0
    else:
        logger.error("\n× MCP GitHub client test FAILED!")
        logger.error("Please check the error messages above and fix the issues.")
        
        # Additional troubleshooting information
        logger.error("\nTroubleshooting tips:")
        logger.error("1. Make sure Node.js and npm are installed")
        logger.error("2. Install the GitHub MCP server with: npm install -g @modelcontextprotocol/server-github")
        logger.error("3. Check your GitHub token is valid and has appropriate permissions")
        logger.error("4. Make sure your .env file contains GITHUB_TOKEN=your_token_here")
        return 1

if __name__ == "__main__":
    sys.exit(main())