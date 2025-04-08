import os
import base64
import re
from github import Github
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DirectGitHubClient:
    """Client that uses PyGithub to interact with repositories directly."""
    
    def __init__(self, github_token=None):
        """
        Initialize client with GitHub token.
        
        Args:
            github_token: GitHub access token (if None, attempts to read from environment)
        """
        token = github_token or os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GitHub token is required. Set it in .env file or pass directly.")
        
        self.github = Github(token)
    
    def list_repository_files(self, owner: str, repo: str, path: str = "", branch: str = None) -> List[Dict[str, Any]]:
        """
        List files in a repository path """
        try:
            repository = self.github.get_repo(f"{owner}/{repo}")
            print(f"successfully got repository {repository.name}")

            try:
                contents = repository.get_contents(path, ref=branch)
                # Handle both single file and directory cases
                if not isinstance(contents, list):
                    contents = [contents]
                    
                result = []
                for content in contents:
                    item = {
                        "name": content.name,
                        "path": content.path,
                        "type": "file" if content.type == "file" else "dir",
                        "size": content.size
                    }
                    result.append(item)
                return result
            except Exception as e:
                error_msg = str(e)
                print(f"Error listing contents at '{path}': {error_msg}")
                raise e
        except Exception as e:
            error_msg = str(e)
            print(f"Error accessing repository '{owner}/{repo}': {error_msg}")
            if "401" in error_msg:
                print("Authentication failed. Check your GitHub token.")
            elif "404" in error_msg:
                print(f"Repository {owner}/{repo} not found or no access.")
            raise e
    
    def get_file_content(self, owner: str, repo: str, path: str, branch: str = None) -> str:
        """
        Get the content of a file.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to the file
            branch: Branch to use (default: repository default branch)
            
        Returns:
            Content of the file as string
        """
        try:
            repository = self.github.get_repo(f"{owner}/{repo}")
            content = repository.get_contents(path, ref=branch)
            
            if content.encoding == "base64":
                return base64.b64decode(content.content).decode('utf-8')
            return content.content
        except Exception as e:
            logger.error(f"Error getting content for file '{path}': {e}")
            raise
    
    def get_repository_structure(self, owner: str, repo: str, branch: str = None, 
                               ignore_dirs: List[str] = None, max_file_size: int = 500000,
                               include_patterns: List[str] = None,
                               extensions: List[str] = None) -> Dict[str, str]:
        """
        Recursively get the structure of a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch to analyze
            ignore_dirs: Directories to ignore
            max_file_size: Maximum file size to include
            include_patterns: Patterns to specifically include
            extensions: File extensions to include
            
        Returns:
            Dictionary mapping file paths to contents
        """

        try:
            repository = self.github.get_repo(f"{owner}/{repo}")
            # If branch is None, use the default branch
            if branch is None:
                branch = repository.default_branch
                print(f"Using default branch: {branch}")
        except Exception as e:
            print(f"Error accessing repository '{owner}/{repo}': {str(e)}")
            print(f"Error type: {type(e).__name__}")
            if hasattr(e, 'status'):
                print(f"HTTP Status: {e.status}")
            # Re-raise the exception to be handled by the calling method
            raise

        if ignore_dirs is None:
            ignore_dirs = ['.git', 'node_modules', '__pycache__', 'dist', 'build']
            
        result = {}
        visited = set()
        
        binary_extensions = [
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.pdf', '.zip', 
            '.gz', '.tar', '.class', '.exe', '.dll', '.so'
        ]
        
        def should_include_file(path: str) -> bool:
            # Check extension filter
            if extensions:
                if not any(path.endswith(ext) for ext in extensions):
                    # Check include patterns as override
                    if include_patterns and any(pattern in path for pattern in include_patterns):
                        return True
                    return False
                
            # Skip binary files
            if any(path.endswith(ext) for ext in binary_extensions):
                return False
                
            return True
        
        def traverse_dir(path: str = ""):
            if path in visited:
                return
                
            visited.add(path)
            
            try:
                items = self.list_repository_files(owner, repo, path, branch)
            except Exception as e:
                logger.error(f"Error listing files in {path}: {e}")
                return
                
            for item in items:
                item_path = item.get("path", "")
                item_type = item.get("type", "")
                item_size = item.get("size", 0)
                
                # Skip ignored directories and their children
                if any(ignored_dir in item_path for ignored_dir in ignore_dirs):
                    logger.debug(f"Skipping ignored directory: {item_path}")
                    continue
                
                if item_type == "dir":
                    # Recursively process directories
                    traverse_dir(item_path)
                    
                elif item_type == "file":
                    # Apply filters
                    if item_size > max_file_size:
                        logger.debug(f"Skipping large file: {item_path} ({item_size} bytes)")
                        continue
                        
                    if not should_include_file(item_path):
                        logger.debug(f"Skipping file based on filters: {item_path}")
                        continue
                    
                    # Fetch file content
                    try:
                        content = self.get_file_content(owner, repo, item_path, branch)
                        result[item_path] = content
                        logger.debug(f"Added file: {item_path}")
                    except Exception as e:
                        logger.error(f"Error getting content for {item_path}: {e}")
        
        # Start traversal from root
        traverse_dir()
        return result