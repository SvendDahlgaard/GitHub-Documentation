import os
from github import Github
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get GitHub token
token = os.getenv('GITHUB_TOKEN')
if not token:
    print("No GitHub token found in .env file")
    exit(1)

try:
    # Initialize GitHub client
    g = Github(token)
    
    # Get authenticated user
    user = g.get_user()
    print(f"Authenticated as: {user.login}")
    
    # Try to access the repository
    repo_name = "SvendDahlgaard/GitHub-Documentation"
    print(f"Trying to access repository: {repo_name}")
    repo = g.get_repo(repo_name)
    print(f"Repository exists: {repo.name}")
    
except Exception as e:
    print(f"Error: {str(e)}")