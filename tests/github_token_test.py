import os
import sys
from github import Github
from dotenv import load_dotenv

def test_github_token():
    """Test GitHub token validity and access to specified repository."""
    # Load environment variables
    load_dotenv()
    
    # Get GitHub token
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("ERROR: No GitHub token found in .env file")
        print("Please create a .env file with GITHUB_TOKEN=your_token")
        return False
    
    try:
        # Initialize GitHub client
        g = Github(token)
        
        # Get authenticated user
        user = g.get_user()
        print(f"✓ Authenticated successfully as: {user.login}")
        
        # Try to access a repository (default is your own repo)
        repo_name = "SvendDahlgaard/GitHub-Documentation"
        print(f"Testing access to repository: {repo_name}")
        repo = g.get_repo(repo_name)
        print(f"✓ Repository access successful: {repo.name}")
        
        # Try to list repository contents
        contents = repo.get_contents("")
        print(f"✓ Successfully listed repository contents ({len(contents)} items)")
        
        # Check rate limits
        rate_limit = g.get_rate_limit()
        print(f"✓ API rate limit status: {rate_limit.core.remaining}/{rate_limit.core.limit} requests remaining")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        if "401" in str(e):
            print("Authentication failed. Your token may be invalid or expired.")
        elif "404" in str(e):
            print(f"Repository {repo_name} not found or you don't have access to it.")
        return False

if __name__ == "__main__":
    print("Testing GitHub token validity...")
    success = test_github_token()
    
    if success:
        print("\nAll tests PASSED! Your GitHub token is valid and working correctly.")
    else:
        print("\nTest FAILED! Please check the error messages above.")
        sys.exit(1)