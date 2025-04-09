import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class RepoCache:
    """
    Cache for storing repository file contents to avoid repeated API calls.
    """
    
    def __init__(self, cache_dir: str = "cache"):
        """
        Initialize the repository cache.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_cache_path(self, owner: str, repo: str, branch: Optional[str] = None) -> str:
        """
        Get the file path for a cached repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name (default: None)
            
        Returns:
            Path to the cache file
        """
        branch_suffix = f"_{branch}" if branch else ""
        return os.path.join(self.cache_dir, f"{owner}_{repo}{branch_suffix}.json")
    
    def get_repo_files(self, owner: str, repo: str, branch: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Get repository files from cache if available.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name (default: None)
            
        Returns:
            Dictionary mapping file paths to contents or None if not cached
        """
        cache_path = self.get_cache_path(owner, repo, branch)
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                logger.info(f"Loaded {len(cache_data)} files from cache for {owner}/{repo}")
                return cache_data
            except Exception as e:
                logger.error(f"Error loading cache for {owner}/{repo}: {e}")
                return None
        
        return None
    
    def cache_repo_files(self, owner: str, repo: str, files: Dict[str, str], branch: Optional[str] = None) -> bool:
        """
        Cache repository files to avoid future API calls.
        
        Args:
            owner: Repository owner
            repo: Repository name
            files: Dictionary mapping file paths to contents
            branch: Branch name (default: None)
            
        Returns:
            True if successfully cached, False otherwise
        """
        cache_path = self.get_cache_path(owner, repo, branch)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(files, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Cached {len(files)} files for {owner}/{repo}")
            return True
        except Exception as e:
            logger.error(f"Error caching repo {owner}/{repo}: {e}")
            return False
    
    def clear_cache(self, owner: Optional[str] = None, repo: Optional[str] = None) -> int:
        """
        Clear cache for a specific repository or all repositories.
        
        Args:
            owner: Repository owner (default: None to clear all)
            repo: Repository name (default: None to clear all owner's repos)
            
        Returns:
            Number of cache files deleted
        """
        count = 0
        
        if owner and repo:
            # Clear specific repo cache
            pattern = f"{owner}_{repo}*.json"
        elif owner:
            # Clear all caches for owner
            pattern = f"{owner}_*.json"
        else:
            # Clear all caches
            pattern = "*.json"
            
        for cache_file in Path(self.cache_dir).glob(pattern):
            try:
                os.remove(cache_file)
                count += 1
            except Exception as e:
                logger.error(f"Error removing cache file {cache_file}: {e}")
                
        return count
