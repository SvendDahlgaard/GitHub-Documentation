from abc import ABC, abstractmethod
import logging
import os
from typing import Dict, List, Tuple, Any, Optional, Set
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

class BaseRepositoryAnalyzer(ABC):
    """
    Abstract base class for repository analysis and clustering.
    Defines common interface and shared functionality for different analysis approaches.
    """
    
    def __init__(self, claude_analyzer=None, use_cache=True):
        """
        Initialize the base repository analyzer.
        
        Args:
            claude_analyzer: Optional Claude analyzer for code analysis
            use_cache: Whether to use caching for results
        """
        self.claude_analyzer = claude_analyzer
        self.use_cache = use_cache
    
    @abstractmethod
    def cluster_repository(self, repo_files: Dict[str, str], 
                           method=None,
                           max_section_size: int = 15,
                           min_section_size: int = 2,
                           auto_filter: bool = True) -> List[Tuple[str, Dict[str, str]]]:
        """
        Analyze repository and divide it into logical sections.
        This method must be implemented by all concrete analyzer classes.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            method: Analysis method to use (implementation-specific)
            max_section_size: Maximum number of files in a section
            min_section_size: Minimum number of files in a section
            auto_filter: Whether to automatically filter less important files
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        pass
    
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
    
    def filter_important_files(self, repo_files: Dict[str, str]) -> Dict[str, str]:
        """
        Basic filter that keeps all code files and important non-code files.
        No Claude/LLM is used in this filtering process.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            
        Returns:
            Filtered dictionary of files
        """
        logger.info("Using basic file filtering")
        
        # Define common code file extensions
        code_extensions = ['.py', '.js', '.java', '.cs', '.ts', '.go', '.rb', '.php', '.cpp', '.c', '.h']
        
        # Files to always exclude
        exclude_patterns = [
            '.gitignore', '.git/', '.github/', '__pycache__/', '.vscode/', '.idea/',
            'node_modules/', 'dist/', 'build/', 'bin/', 'obj/',
            '.pyc', '.pyo', '.dll', '.exe', '.o', '.so', '.a', '.lib',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
            '.min.js', '.min.css'
        ]
        
        # Important file patterns to keep regardless of extension
        important_patterns = [
            'readme', 'license', 'config', 'setup', 'environment',
            'docker', 'kubernetes', 'deployment', 'ci', 'cd',
            'requirements.txt', 'package.json', 'gemfile', 'csproj',
            'main', 'app', 'index', 'server', 'client'
        ]
        
        filtered_files = {}
        
        for path, content in repo_files.items():
            # Skip excluded files
            if any(exclude in path.lower() for exclude in exclude_patterns):
                continue
                
            # Keep if it's a code file
            extension = os.path.splitext(path)[1].lower()
            if extension in code_extensions:
                filtered_files[path] = content
                continue
                
            # Keep if it matches important patterns
            if any(pattern in path.lower() for pattern in important_patterns):
                filtered_files[path] = content
                continue
        
        logger.info(f"Basic filter kept {len(filtered_files)} files out of {len(repo_files)} total")
        return filtered_files
    
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
    
    def _analyze_with_claude(self, content: Dict[str, str], query: str, section_name: str, context: Optional[str] = None) -> str:
        """
        Helper method to analyze content with Claude if available.
        
        Args:
            content: Dictionary mapping file paths to contents
            query: Question to ask Claude about the content
            section_name: Name of the section (for logging)
            context: Optional context from previous analyses
            
        Returns:
            Analysis result from Claude or error message
        """
        if not self.claude_analyzer:
            return "Claude analyzer not available"
            
        try:
            # Format the section for Claude
            section = [(section_name, content)]
            
            # Create context map if context provided
            context_map = None
            if context:
                context_map = {section_name: context}
            
            # Send to Claude using the analyze_sections_batch method of the batch analyzer
            results = self.claude_analyzer.analyze_sections_batch(
                sections=section,
                query=query,
                context_map=context_map
            )
            
            # Extract result
            if section_name in results:
                analysis = results[section_name]
                
                # Check if we got an error
                if analysis.startswith("Error:"):
                    logger.error(f"Error analyzing {section_name}: {analysis}")
                    return f"Analysis failed: {analysis}"
                
                return analysis
            else:
                logger.error(f"No result returned for {section_name}")
                return "Analysis failed: No result returned"
            
        except Exception as e:
            logger.error(f"Exception analyzing {section_name}: {str(e)}")
            return f"Analysis failed: {str(e)}"