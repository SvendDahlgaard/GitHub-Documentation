#!/usr/bin/env python3
"""
Test script for GitHub access and repository analyzer functionality.
"""
import os
import sys
from github import Github
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def test_github_token():
    """Test GitHub token validity and access to repositories."""
    # Load environment variables
    load_dotenv()
    
    # Get GitHub token
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        logger.error("No GitHub token found in .env file")
        logger.error("Please create a .env file with GITHUB_TOKEN=your_token")
        return False
    
    try:
        # Initialize GitHub client
        g = Github(token)
        
        # Get authenticated user
        user = g.get_user()
        logger.info(f"Authenticated as: {user.login}")
        
        # Try to access the repository
        repo_name = "SvendDahlgaard/GitHub-Documentation"
        logger.info(f"Trying to access repository: {repo_name}")
        repo = g.get_repo(repo_name)
        logger.info(f"Repository exists: {repo.name}")
        
        # List repository contents
        contents = repo.get_contents("")
        logger.info(f"Successfully listed repository contents ({len(contents)} items)")
        
        # Check rate limits
        rate_limit = g.get_rate_limit()
        logger.info(f"API rate limit status: {rate_limit.core.remaining}/{rate_limit.core.limit} requests remaining")
        
        return True
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if "401" in str(e):
            logger.error("Authentication failed. Your token may be invalid or expired.")
        elif "404" in str(e):
            logger.error(f"Repository {repo_name} not found or you don't have access to it.")
        return False

def test_section_analyzer():
    """Test section analyzer functionality on a GitHub repository."""
    try:
        from direct_github_client import DirectGitHubClient
        from section_analyzer import SectionAnalyzer
        
        # Import was successful
        logger.info("Successfully imported repository analyzer modules")
        return True
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure all required modules are installed")
        return False

def run_quick_tests():
    """Run quick tests to verify setup."""
    github_result = test_github_token()
    modules_result = test_section_analyzer()
    
    if github_result and modules_result:
        logger.info("All quick tests passed!")
        logger.info("For full testing, run the tests in the tests/ directory")
        return True
    else:
        logger.error("Some tests failed. Please check the output above.")
        return False

if __name__ == "__main__":
    success = run_quick_tests()
    if not success:
        sys.exit(1)