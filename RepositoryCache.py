import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List, Set, Tuple, Any
from collections import defaultdict

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
        self.structure_dir = os.path.join(cache_dir, "structure")
        
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(self.structure_dir, exist_ok=True)
    
    def get_cache_path(self, owner: str, repo: str) -> str:
        """
        Get the file path for a cached repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Path to the cache file
        """
        return os.path.join(self.cache_dir, f"{owner}_{repo}.json")
    
    def get_structure_path(self, owner: str, repo: str) -> str:
        """
        Get the file path for cached repository structure information.
            
        Returns:
            Path to the structure file
        """
        return os.path.join(self.structure_dir, f"{owner}_{repo}_structure.json")
    
    def get_repo_files(self, owner: str, repo: str) -> Optional[Dict[str, str]]:
        """
        Get repository files from cache if available.
            
        Returns:
            Dictionary mapping file paths to contents or None if not cached
        """
        cache_path = self.get_cache_path(owner, repo)
        
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
    
    def cache_repo_files(self, owner: str, repo: str, files: Dict[str, str]) -> bool:
        """
        Cache repository files to avoid future API calls.
        
        Args:
            files: Dictionary mapping file paths to contents
            
        Returns:
            True if successfully cached, False otherwise
        """
        cache_path = self.get_cache_path(owner, repo)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(files, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Cached {len(files)} files for {owner}/{repo}")
            
            # When caching files, also update the repository structure cache
            self.cache_repo_structure(owner, repo, files)
            
            return True
        except Exception as e:
            logger.error(f"Error caching repo {owner}/{repo}: {e}")
            return False
    
    def cache_repo_structure(self, owner: str, repo: str, files: Dict[str, str]) -> bool:
        """
        Update the repository structure cache based on file paths.
        
        Args:
            files: Dictionary mapping file paths to contents
            
        Returns:
            True if successfully cached, False otherwise
        """
        structure_path = self.get_structure_path(owner, repo)
        
        try:
            # Build directory structure from file paths
            dir_structure = self._build_directory_structure(files)
            
            # Add additional metadata
            structure_data = {
                "owner": owner,
                "repo": repo,
                "file_count": len(files),
                "timestamp": time.time(),
                "directory_structure": dir_structure,
                "file_extensions": self._collect_file_extensions(files)
            }
            
            with open(structure_path, 'w', encoding='utf-8') as f:
                json.dump(structure_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Updated structure cache for {owner}/{repo}")
            return True
        except Exception as e:
            logger.error(f"Error updating structure cache for {owner}/{repo}: {e}")
            return False
    
    def get_repo_structure(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Get repository structure information from cache if available.
            
        Returns:
            Dictionary with directory structure information or None if not cached
        """
        structure_path = self.get_structure_path(owner, repo)
        
        if os.path.exists(structure_path):
            try:
                with open(structure_path, 'r', encoding='utf-8') as f:
                    structure_data = json.load(f)
                    
                logger.info(f"Loaded repository structure from cache for {owner}/{repo}")
                return structure_data
            except Exception as e:
                logger.error(f"Error loading structure cache for {owner}/{repo}: {e}")
                return None
        
        # If structure cache doesn't exist but file cache does, generate structure
        files = self.get_repo_files(owner, repo)
        if files:
            if self.cache_repo_structure(owner, repo, files):
                return self.get_repo_structure(owner, repo)
        
        return None
    
    def get_directory_files(self, owner: str, repo: str, directory: str) -> List[str]:
        """
        Get list of files in a specific directory from the cached repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            directory: Directory path within the repository 

        Returns:
            List of file paths in the directory
        """
        # Remove leading and trailing slashes for consistency
        directory = directory.strip("/")
        
        # Get the repository files
        files = self.get_repo_files(owner, repo)
        if not files:
            return []
        
        # Filter files by directory
        directory_files = []
        for path in files.keys():
            path_dir = os.path.dirname(path)
            # Check if this file is in the specified directory or a subdirectory
            if path_dir == directory or path_dir.startswith(f"{directory}/"):
                directory_files.append(path)
        
        return directory_files
    
    def clear_cache(self, owner: Optional[str] = None, repo: Optional[str] = None) -> int:
        """
        Clear cache for a specific repository or all repositories.
            
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
        
        # Clear from all cache directories
        cache_dirs = [self.cache_dir, self.structure_dir]
        
        for directory in cache_dirs:
            for cache_file in Path(directory).glob(pattern):
                try:
                    os.remove(cache_file)
                    count += 1
                except Exception as e:
                    logger.error(f"Error removing cache file {cache_file}: {e}")         
        return count
    
    def _build_directory_structure(self, files: Dict[str, str]) -> Dict[str, Any]:
        """
        Build a hierarchical directory structure from file paths.
        
        Args:
            files: Dictionary mapping file paths to contents
            
        Returns:
            Nested dictionary representing directory structure
        """
        # Create a nested dictionary where each key is a directory or file
        dir_structure = {}
        
        for path in files.keys():
            # Split path into components
            parts = Path(path).parts
            
            # Navigate the tree, creating directories as needed
            current = dir_structure
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Last part (file)
                    current[part] = {"type": "file", "path": path}
                else:  # Directory
                    if part not in current:
                        current[part] = {"type": "directory", "children": {}}
                    
                    # Move to children
                    current = current[part]["children"]
        
        return dir_structure
    
    def _collect_file_extensions(self, files: Dict[str, str]) -> Dict[str, int]:
        """
        Collect statistics on file extensions in the repository.
            
        Returns:
            Dictionary mapping file extensions to counts
        """
        extensions = defaultdict(int)
        
        for path in files.keys():
            ext = os.path.splitext(path)[1].lower()
            if not ext:
                ext = "[no extension]"
            extensions[ext] += 1
            
        return dict(extensions)
