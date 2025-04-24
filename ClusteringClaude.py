import os
import json
import logging
import re
from typing import Dict, List, Tuple, Set, Optional, Any
from collections import defaultdict
import networkx as nx

from BaseClusteringAbstractClass import BaseRepositoryAnalyzer

logger = logging.getLogger(__name__)

class LLMClusterAnalyzer(BaseRepositoryAnalyzer):
    """
    Analyze repository files using LLM-based clustering to create logical code sections.
    This approach leverages Claude's code understanding to group files based on functional relationships.
    """
    
    def __init__(self, batch_analyzer=None, use_cache=True, max_batch_size=10, clustering_model=None):
        """
        Initialize the LLM cluster analyzer.
        
        Args:
            batch_analyzer: BatchClaudeAnalyzer instance for efficient LLM queries
            use_cache: Whether to use caching for clustering results
            max_batch_size: Maximum number of files to process in a batch
            clustering_model: Claude model to use for clustering
        """
        super().__init__(batch_analyzer, use_cache)
        self.max_batch_size = max_batch_size
        self.clustering_model = clustering_model or "claude-3-5-haiku-20241022"

    
    def cluster_repository(self, repo_files: Dict[str, str], 
                          method=None,  # Not used but included for interface consistency
                          max_section_size: int = 15,
                          min_section_size: int = 2,
                          auto_filter: bool = True) -> List[Tuple[str, Dict[str, str]]]:
        """
        Analyze repository using LLM-based clustering.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            method: Not used, included for interface consistency with BasicSectionAnalyzer
            max_section_size: Maximum number of files in a section
            min_section_size: Minimum number of files in a section
            auto_filter: Whether to automatically filter less important files
  
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        logger.info("Performing LLM-based clustering analysis")
        
        # If auto_filter is enabled, filter less important files first
        if auto_filter:
            repo_files = self.filter_important_files(repo_files)
            logger.info(f"Filtered to {len(repo_files)} important files for analysis")
        
        # Step 1: Create initial grouping by directory (for efficiency)
        dir_groups = defaultdict(dict)
        for path, content in repo_files.items():
            dir_name = os.path.dirname(path) or "root"
            dir_groups[dir_name][path] = content
        
        sections = []
        
        # Step 2: Process each directory group
        for dir_name, files in dir_groups.items():
            logger.info(f"Processing directory group: {dir_name} with {len(files)} files")
            
            # If directory has few files, keep as is
            if len(files) <= max_section_size:
                sections.append((dir_name, files))
                continue
            
            # For larger directories, use LLM clustering
            file_summaries = self._summarize_files(files)
            
            # Generate clusters using LLM
            clusters = self._generate_clusters(dir_name, file_summaries, files, max_section_size)
            
            # Convert clusters to sections
            for cluster_name, file_paths in clusters.items():
                section_name = f"{dir_name}/{cluster_name}" if dir_name != "root" else cluster_name
                section_files = {path: files[path] for path in file_paths if path in files}
                if section_files:
                    sections.append((section_name, section_files))
        
        # Apply minimum section size
        if min_section_size > 1:
            sections = self._merge_small_sections(sections, min_section_size)
        
        return sorted(sections, key=lambda x: x[0])
    
    def _summarize_files(self, files: Dict[str, str]) -> Dict[str, str]:
        """
        Generate summaries for each file using batch processing.
        
        Args:
            files: Dictionary mapping file paths to contents
            
        Returns:
            Dictionary mapping file paths to summaries
        """
        logger.info(f"Generating summaries for {len(files)} files")
        
        # Process files in batches to avoid overwhelmingly large requests
        file_paths = list(files.keys())
        file_summaries = {}
        
        for i in range(0, len(file_paths), self.max_batch_size):
            batch = file_paths[i:i+self.max_batch_size]
            logger.info(f"Processing summary batch {i//self.max_batch_size + 1}/{(len(file_paths) + self.max_batch_size - 1)//self.max_batch_size}")
            
            # Process each file individually using our base service
            for path in batch:
                content = files[path]
                
                # Create a summarization prompt
                summary_prompt = "Provide a very brief summary focusing only on the primary purpose of this file, key functions/classes, and its relationships with other components."
                
                # Format file content
                file_ext = os.path.splitext(path)[1]
                file_content = {
                    "file.txt": f"Path: {path}\nType: {file_ext} file\n\n```\n{content}\n```"
                }
                
                # Analyze using Claude
                summary = self._analyze_with_claude(
                    content=file_content,
                    query=summary_prompt,
                    section_name=path
                )
                
                # Store the summary
                file_summaries[path] = summary
        
        logger.info(f"Successfully generated {len(file_summaries)} file summaries")
        return file_summaries
    
    def _generate_clusters(self, dir_name: str, file_summaries: Dict[str, str], 
                         original_files: Dict[str, str],
                         max_cluster_size: int) -> Dict[str, List[str]]:
        """
        Generate clusters of related files using LLM.
        
        Args:
            dir_name: Directory name these files belong to
            file_summaries: Dictionary mapping file paths to summaries
            original_files: Dictionary mapping file paths to original content
            max_cluster_size: Maximum size of each cluster
            
        Returns:
            Dictionary mapping cluster names to lists of file paths
        """
        logger.info(f"Generating clusters for {len(file_summaries)} files in directory: {dir_name}")
        
        # Create a prompt that includes all summaries
        summary_text = ""
        for path, summary in file_summaries.items():
            file_name = os.path.basename(path)
            summary_text += f"\n\nFile: {file_name}\nPath: {path}\nSummary: {summary}"
        
        # Calculate the ideal number of clusters based on file count and max size
        total_files = len(file_summaries)
        min_clusters = max(2, (total_files + max_cluster_size - 1) // max_cluster_size)
        max_clusters = max(3, min(total_files // 2, 10))  # Don't create too many small clusters
        
        # The clustering prompt with clear JSON output instructions
        clustering_prompt = f"""You are helping analyze a codebase for documentation purposes.
Based on these file summaries from the '{dir_name}' directory, group these files into logical clusters of related functionality.

{summary_text}

Rules:
1. Create between {min_clusters} and {max_clusters} distinct clusters
2. No cluster should contain more than {max_cluster_size} files
3. Group files based on functional relationships, shared dependencies, and similar purposes

Format your response as a valid JSON object with cluster names as keys and arrays of file paths as values. Example:
```json
{{
  "cluster_name_1": ["file/path1.py", "file/path2.py"],
  "cluster_name_2": ["file/path3.py", "file/path4.py"]
}}
```

Choose descriptive cluster names that reflect the purpose of the grouped files.
"""

        # Prepare content for Claude
        content = {"clustering_request.md": clustering_prompt}
        
        # Get clustering from Claude
        clustering_response = self._analyze_with_claude(
            content=content,
            query="Group these files into logical clusters based on functionality.",
            section_name=f"cluster_{dir_name}"
        )
        
        # Extract JSON from response
        try:
            # Find JSON block in the response
            json_start = clustering_response.find('{')
            json_end = clustering_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = clustering_response[json_start:json_end]
                clusters = json.loads(json_str)
                logger.info(f"Successfully generated {len(clusters)} clusters")
                return clusters
            else:
                # Try to find JSON in code blocks
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', 
                                    clustering_response, re.DOTALL)
                if json_match:
                    clusters = json.loads(json_match.group(1))
                    logger.info(f"Successfully extracted {len(clusters)} clusters from code block")
                    return clusters
                
                logger.error("Could not find JSON in the response")
                return self._fallback_clustering(file_summaries, original_files, max_cluster_size)
                
        except Exception as e:
            logger.error(f"Error parsing clustering result: {e}")
            # Fallback to simple clustering
            return self._fallback_clustering(file_summaries, original_files, max_cluster_size)
    
    def _fallback_clustering(self, file_summaries: Dict[str, str], 
                           original_files: Dict[str, str],
                           max_cluster_size: int) -> Dict[str, List[str]]:
        """
        Fallback method for clustering when LLM fails.
        
        Args:
            file_summaries: Dictionary mapping file paths to summaries
            original_files: Dictionary mapping file paths to original content
            max_cluster_size: Maximum size of each cluster
            
        Returns:
            Dictionary mapping cluster names to lists of file paths
        """
        logger.warning("Using fallback clustering method")
        
        # Try directory-based grouping first
        subdir_groups = defaultdict(list)
        for path in file_summaries.keys():
            subdir = os.path.dirname(path)
            if '/' in subdir:
                # Use second-level directory
                subdir = subdir.split('/', 1)[1]
            subdir_groups[subdir or "main"].append(path)
        
        # If we have reasonable groupings, use them
        if subdir_groups and all(len(files) <= max_cluster_size for files in subdir_groups.values()):
            return {f"{name}_files": files for name, files in subdir_groups.items()}
        
        # Otherwise, group by file extension
        ext_groups = defaultdict(list)
        for path in file_summaries.keys():
            ext = os.path.splitext(path)[1] or "unknown"
            if ext.startswith('.'):
                ext = ext[1:]
            ext_groups[f"{ext}_files"].append(path)
        
        # Split any oversized clusters
        final_clusters = {}
        for cluster_name, paths in ext_groups.items():
            if len(paths) <= max_cluster_size:
                final_clusters[cluster_name] = paths
            else:
                # Split into smaller chunks
                chunk_count = (len(paths) + max_cluster_size - 1) // max_cluster_size
                for i in range(chunk_count):
                    start = i * max_cluster_size
                    end = min((i + 1) * max_cluster_size, len(paths))
                    final_clusters[f"{cluster_name}_part{i+1}"] = paths[start:end]
        
        return final_clusters