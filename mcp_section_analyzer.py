import os
import logging
from typing import List, Dict, Tuple, Set, Optional, Any
from collections import defaultdict
import re
import networkx as nx

from section_analyzer import SectionAnalyzer, AnalysisMethod
from mcp_github_client import MCPGitHubClient

logger = logging.getLogger(__name__)

class MCPSectionAnalyzer(SectionAnalyzer):
    """Section analyzer with enhanced capabilities using MCP GitHub client."""
    
    def __init__(self, claude_analyzer=None, mcp_client=None):
        """
        Initialize the MCP-enhanced section analyzer.
        
        Args:
            claude_analyzer: The Claude analyzer for code analysis
            mcp_client: The MCP GitHub client for repository interactions
        """
        super().__init__(claude_analyzer)
        self.mcp_client = mcp_client or MCPGitHubClient()
        
    def enhanced_dependency_analysis(self, repo_files: Dict[str, str], owner: str, repo: str, 
                                  max_section_size: int = 15) -> List[Tuple[str, Dict[str, str]]]:
        """
        Analyze repository using enhanced dependency detection via code search.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            owner: Repository owner
            repo: Repository name
            max_section_size: Maximum number of files in a section before subdivision
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        logger.info("Performing enhanced dependency analysis with code search")
        
        # Build dependency graph using code search
        dependencies = self._extract_enhanced_dependencies(repo_files, owner, repo)
        
        # Create a directed graph of dependencies
        G = nx.DiGraph()
        
        # Add all files as nodes
        for path in repo_files.keys():
            G.add_node(path)
        
        # Add edges based on dependencies
        for source, targets in dependencies.items():
            for target in targets:
                if target in repo_files:  # Only add edges to files we have
                    G.add_edge(source, target)
        
        # Find strongly connected components (files that form cycles)
        try:
            components = list(nx.strongly_connected_components(G))
        except Exception as e:
            logger.warning(f"NetworkX strongly connected components failed: {e}, using alternative grouping")
            return self._fallback_dependency_grouping(repo_files, dependencies, max_section_size)
        
        # Build initial sections from connected components
        sections = []
        unassigned_files = set(repo_files.keys())
        
        # First, handle strongly connected components
        for i, component in enumerate(components):
            if len(component) > 1:  # Only use components with at least 2 files
                component_files = {path: repo_files[path] for path in component if path in repo_files}
                if component_files:
                    # Use a common prefix if available
                    prefix = self._find_common_prefix(component_files.keys())
                    section_name = f"{prefix}_component_{i+1}" if prefix else f"component_{i+1}"
                    sections.append((section_name, component_files))
                    unassigned_files -= component_files.keys()
        
        # Then, assign remaining files to sections based on common imports
        if unassigned_files:
            modular_sections = self._group_by_dependencies(
                {path: repo_files[path] for path in unassigned_files},
                dependencies,
                max_section_size
            )
            sections.extend(modular_sections)
        
        # Further divide large sections
        final_sections = []
        for section_name, files in sections:
            if len(files) > max_section_size:
                # Try to subdivide large sections
                subdivisions = self._subdivide_section(section_name, files, max_section_size)
                final_sections.extend(subdivisions)
            else:
                final_sections.append((section_name, files))
        
        return sorted(final_sections, key=lambda x: x[0])
        
    def _extract_enhanced_dependencies(self, repo_files: Dict[str, str], owner: str, repo: str) -> Dict[str, Set[str]]:
        """
        Extract enhanced dependencies between files using code search.
        
        Args:
            repo_files: Dictionary of file paths to contents
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Dictionary mapping file paths to sets of imported/referenced file paths
        """
        # Start with basic dependencies
        dependencies = self._extract_dependencies(repo_files)
        
        # Enhance with code search-based dependencies
        try:
            for filepath in list(repo_files.keys()):
                # Search for references to this file
                references = self.mcp_client.search_references(owner, repo, filepath)
                
                # Add reverse dependencies (files that reference this file)
                for ref_path in references:
                    if ref_path in repo_files:
                        dependencies[ref_path].add(filepath)
                
                # Log progress for larger repositories
                if len(repo_files) > 50 and len(dependencies) % 10 == 0:
                    logger.info(f"Processed {len(dependencies)}/{len(repo_files)} files for dependencies")
                
        except Exception as e:
            logger.warning(f"Code search-based dependency enhancement failed: {e}")
            logger.warning("Falling back to basic dependency extraction")
        
        return dependencies
    
    def analyze_repository(self, repo_files: Dict[str, str], 
                         method: AnalysisMethod = AnalysisMethod.STRUCTURAL,
                         max_section_size: int = 15,
                         min_section_size: int = 2,
                         owner: str = None,
                         repo: str = None) -> List[Tuple[str, Dict[str, str]]]:
        """
        Analyze repository using the specified method with MCP enhancements when possible.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            method: Analysis method to use
            max_section_size: Maximum number of files in a section before subdivision
            min_section_size: Minimum number of files in a section (smaller sections will be merged)
            owner: Repository owner (required for enhanced analysis)
            repo: Repository name (required for enhanced analysis)
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        # If we have owner and repo info, we can use enhanced dependency analysis
        if method == AnalysisMethod.DEPENDENCY and owner and repo:
            logger.info(f"Using enhanced dependency analysis for {owner}/{repo}")
            sections = self.enhanced_dependency_analysis(repo_files, owner, repo, max_section_size)
        else:
            # Fall back to standard analysis methods
            sections = super().analyze_repository(repo_files, method, max_section_size)
        
        # Apply minimum section size if specified
        if min_section_size > 1:
            sections = self._merge_small_sections(sections, min_section_size)
            
        return sections
