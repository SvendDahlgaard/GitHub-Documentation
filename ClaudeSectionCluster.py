import os
import json
import logging
from typing import Dict, List, Tuple, Set, Optional, Any
from collections import defaultdict
import networkx as nx

from ClaudeClientAPI import OptimizedPromptManager

logger = logging.getLogger(__name__)

class LLMClusterAnalyzer:
    """
    Analyze repository files using LLM-based clustering to create logical code sections.
    This approach leverages Claude's code understanding to group files based on functional relationships.
    """
    
    def __init__(self, batch_analyzer=None, use_cache=True, max_batch_size=10, clustering_model = None):
        """
        Initialize the LLM cluster analyzer.
        
        Args:
            batch_analyzer: BatchClaudeAnalyzer instance for efficient LLM queries
            use_cache: Whether to use caching for clustering results
            max_batch_size: Maximum number of files to process in a batch
        """
        self.batch_analyzer = batch_analyzer
        self.use_cache = use_cache
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
        
        # Step 1: Create initial grouping by directory (for efficiency)
        dir_groups = defaultdict(dict)
        for path, content in repo_files.items():
            dir_name = os.path.dirname(path) or "root"
            dir_groups[dir_name][path] = content

            # If auto_filter is enabled, filter less important files first
        if auto_filter:
            repo_files = self._filter_important_files(repo_files)
            logger.info(f"Filtered to {len(repo_files)} important files for analysis")
        
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
            
            # Prepare batch sections for the analyzer
            batch_sections = []
            
            for path in batch:
                content = files[path]
                # Create a summarization prompt for this file
                summary_prompt = self._create_summarization_prompt(path, content)
                # Add to batch sections with the path as the section name
                batch_sections.append((path, {"file.txt": content, "prompt.md": summary_prompt}))
            
            # Process this batch
            batch_results = self.batch_analyzer.analyze_sections_batch(batch_sections, 
                "Summarize this file briefly, focusing on its purpose and relationships to other components.", model = self.clustering_model)
            
            # Add results to the overall summaries
            file_summaries.update(batch_results)
        
        logger.info(f"Successfully generated {len(file_summaries)} file summaries")
        return file_summaries
    
    def _create_summarization_prompt(self, path: str, content: str) -> str:
        """Create a prompt for file summarization."""
        # Limit content preview to avoid excessive token usage
        file_preview = content[:2000] + "..." if len(content) > 2000 else content
        extension = os.path.splitext(path)[1]
        
        return f"""Analyze this file:
Path: {path}
Type: {extension} file

Content (preview):
```
{file_preview}
```

Provide a very brief summary focusing only on:
1. The primary purpose of this file
2. Key functions, classes, or data structures
3. Dependencies and relationships with other components

Keep your response short and focused on technical details only."""
    
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
        
        # The clustering prompt - optimized for Claude to return structured data
        clustering_prompt = f"""Below are summaries of files in the '{dir_name}' directory:

{summary_text}

Based on these summaries, group these files into logical clusters of related functionality.
Rules:
1. Create between {min_clusters} and {max_clusters} distinct clusters
2. No cluster should contain more than {max_cluster_size} files
3. Group files based on:
   - Functional relationships (files that work together)
   - Shared dependencies
   - Similar purposes

Format your response as a valid JSON object with cluster names as keys and arrays of file paths as values:

```json
{{
  "cluster_name_1": ["file/path1.py", "file/path2.py"],
  "cluster_name_2": ["file/path3.py", "file/path4.py"]
}}
```

Choose descriptive cluster names that reflect the purpose of the grouped files.
"""
        
        # Create a single section for the clustering request
        clustering_section = [(f"cluster_{dir_name}", {"clustering_prompt.md": clustering_prompt})]
        
        #clustering_model = "claude-3-5-haiku-20241022"
        # Use the batch analyzer to get the clustering result
        result = self.batch_analyzer.analyze_sections_batch(
            sections = clustering_section, 
            query = "Group these files into logical clusters based on functionality.",
            model = self.clustering_model
            )
        
        # Extract JSON response (with error handling)
        try:
            clustering_response = result.get(f"cluster_{dir_name}", "")
            # Extract JSON from response
            json_str = OptimizedPromptManager.extract_json(clustering_response)
            clusters = json.loads(json_str)
            
            logger.info(f"Successfully generated {len(clusters)} clusters")
            return clusters
        except Exception as e:
            logger.error(f"Error parsing clustering result: {e}")
            # Fallback to simple clustering
            return self._fallback_clustering(file_summaries, original_files, max_cluster_size)
        
    def _filter_important_files(self, repo_files: Dict[str, str]) -> Dict[str, str]:
        """
        Use Claude to determine which files are most important for documentation.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            
        Returns:
            Filtered dictionary of important files
        """
        # Prepare file metadata for all files
        file_metadata = []
        for path, content in repo_files.items():
            extension = os.path.splitext(path)[1]
            file_metadata.append({
                "path": path,
                "extension": extension,
                "size": len(content),
                "lines": content.count('\n') + 1,
                "is_test": "test" in path.lower() or path.startswith("tests/"),
                "preview": content[:300] + "..." if len(content) > 300 else content
            })
        
        # Create batch of metadata for analysis
        metadata_json = json.dumps(file_metadata)
        
        # Create a prompt for Claude to evaluate file importance
        importance_prompt = f"""You are helping analyze a codebase for documentation purposes.
    Below is metadata about files in the repository. Determine which files are most important
    to include in documentation and which can be safely excluded.

    Important files typically include:
    - Core functionality and business logic
    - Main interfaces and APIs
    - Configuration and setup files
    - Type definitions and data models

    Less important files typically include:
    - Auto-generated code
    - Trivial configuration files (like .gitignore)
    - Test fixtures and test output
    - Duplicate or near-duplicate files
    - Very small utility files with minimal content

    File metadata:
    {metadata_json}

    Return a JSON array of paths for files that SHOULD be included in documentation.
    Format: ["file1.py", "file2.js", ...]
    """
        
        # Create a single section for the importance evaluation
        importance_section = [("file_importance", {"importance_prompt.md": importance_prompt})]
        
        # Use the batch analyzer to get the evaluation
        result = self.batch_analyzer.analyze_sections_batch(
            importance_section, 
            "Evaluate which files are most important for documentation.",
            model = self.clustering_model
        )
        
        # Extract JSON response (with error handling)
        try:
            importance_response = result.get("file_importance", "")
            # Extract JSON array from response
            json_str = OptimizedPromptManager.extract_json(importance_response)
            important_paths = json.loads(json_str)
            
            # Filter repo_files to only include important paths
            important_files = {path: content for path, content in repo_files.items() 
                            if path in important_paths}
            
            logger.info(f"Identified {len(important_files)} important files out of {len(repo_files)} total")
            
            # If too few files were selected, return all files
            if len(important_files) < 0.3 * len(repo_files):
                logger.warning("Too few important files identified, using all files")
                return repo_files
                
            return important_files
        except Exception as e:
            logger.error(f"Error determining file importance: {e}")
            # Fall back to using all files
            return repo_files
    
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
    
    def _merge_small_sections(self, sections: List[Tuple[str, Dict[str, str]]], 
                           min_size: int) -> List[Tuple[str, Dict[str, str]]]:
        """
        Merge sections that are smaller than the minimum size.
        
        Args:
            sections: List of (section_name, files) tuples
            min_size: Minimum number of files in a section
            
        Returns:
            List of merged sections
        """
        if min_size <= 1:
            return sections
            
        # Separate large and small sections
        large_sections = []
        small_sections = []
        
        for name, files in sections:
            if len(files) >= min_size:
                large_sections.append((name, files))
            else:
                small_sections.append((name, files))
        
        if not small_sections:
            return large_sections
            
        # Group small sections by parent category
        parent_groups = defaultdict(list)
        for name, files in small_sections:
            # Use first part of the section name as the parent category
            parent = name.split('/')[0]
            parent_groups[parent].append((name, files))
        
        # Merge small sections within the same parent category
        merged_sections = []
        for parent, group_sections in parent_groups.items():
            if not group_sections:
                continue
                
            # Merge files from all sections in this group
            merged_files = {}
            for _, files in group_sections:
                merged_files.update(files)
            
            # If the merged section is large enough, add it
            if len(merged_files) >= min_size:
                # Create a name based on the parent and number of merged sections
                if len(group_sections) > 1:
                    merged_name = f"{parent}/merged_{len(group_sections)}_sections"
                else:
                    merged_name = group_sections[0][0]
                merged_sections.append((merged_name, merged_files))
            else:
                # If still too small, add to a pending list for further merging
                merged_sections.append((f"{parent}/small_files", merged_files))
        
        # Final step: handle any remaining small sections
        final_merged_sections = []
        misc_files = {}
        
        for name, files in merged_sections:
            if len(files) >= min_size:
                final_merged_sections.append((name, files))
            else:
                # Add to miscellaneous bucket
                misc_files.update(files)
        
        # If we have miscellaneous files, create a section for them
        if misc_files:
            final_merged_sections.append(("miscellaneous", misc_files))
        
        # Return large sections plus merged small sections
        return large_sections + final_merged_sections
    
    def create_section_index(self, sections: List[Tuple[str, Dict[str, str]]], analyses: Dict[str, str]) -> str:
        """
        Create an index/directory of all analyzed sections with links.
        
        Args:
            sections: List of (section_name, files) tuples
            analyses: Dictionary mapping section names to their analyses
            
        Returns:
            Markdown index document
        """
        # Build a table of contents
        toc_parts = ["# Repository Analysis Index\n\n"]
        toc_parts.append("## Sections\n\n")
        
        # Group sections by top-level directory
        grouped_sections = defaultdict(list)
        for section_name, _ in sections:
            top_level = section_name.split('/')[0]
            grouped_sections[top_level].append(section_name)
        
        # Add TOC entries for each group
        for group, section_names in sorted(grouped_sections.items()):
            toc_parts.append(f"### {group}\n\n")
            for section_name in sorted(section_names):
                # Get file count
                _, files = next((s, f) for s, f in sections if s == section_name)
                file_count = len(files)
                
                # Create a sanitized anchor link
                anchor = section_name.replace('/', '_').replace('.', '_').lower()
                toc_parts.append(f"- [{section_name}](#{anchor}) ({file_count} files)\n")
            toc_parts.append("\n")
        
        # Add section analyses
        toc_parts.append("## Analysis by Section\n\n")
        
        for section_name, files in sections:
            anchor = section_name.replace('/', '_').replace('.', '_').lower()
            toc_parts.append(f"<h3 id='{anchor}'>{section_name} ({len(files)} files)</h3>\n\n")
            
            # List the files in this section
            toc_parts.append("**Files:**\n\n")
            for path in sorted(files.keys()):
                toc_parts.append(f"- `{path}`\n")
            toc_parts.append("\n")
            
            # Add the analysis
            if section_name in analyses:
                toc_parts.append("**Analysis:**\n\n")
                toc_parts.append(analyses[section_name])
                toc_parts.append("\n\n---\n\n")
            else:
                toc_parts.append("*No analysis available for this section.*\n\n---\n\n")
        
        return "".join(toc_parts)