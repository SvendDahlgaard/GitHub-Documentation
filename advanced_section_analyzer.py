import os
import logging
from typing import List, Dict, Tuple, Set, Optional, Any
from collections import defaultdict
import re
import networkx as nx

from section_analyzer import SectionAnalyzer, AnalysisMethod
from repo_cache import RepoCache

logger = logging.getLogger(__name__)

class AdvancedSectionAnalyzer(SectionAnalyzer):
    """Advanced section analyzer with enhanced capabilities using MCP GitHub client."""
    
    def __init__(self, claude_analyzer=None, mcp_client=None, use_cache=True):
        """
        Initialize the advanced section analyzer.
        
        Args:
            claude_analyzer: The Claude analyzer for code analysis
            mcp_client: The MCP GitHub client for repository interactions
            use_cache: Whether to use caching for dependency information
        """
        super().__init__(claude_analyzer)
        self.mcp_client = mcp_client 
        self.use_cache = use_cache
        self.cache = RepoCache() if use_cache else None
        
    def enhanced_dependency_analysis(self, repo_files: Dict[str, str], owner: str, repo: str, 
                                  max_section_size: int = 15,
                                  branch: str = None) -> List[Tuple[str, Dict[str, str]]]:
        """
        Analyze repository using enhanced dependency detection via code search.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            owner: Repository owner
            repo: Repository name
            max_section_size: Maximum number of files in a section before subdivision
            branch: Repository branch
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        logger.info("Performing enhanced dependency analysis with code search")
        
        # Check if we have cached dependencies
        dependencies = None
        dependency_cache_key = f"{owner}_{repo}_{branch}_dependencies"
        if self.use_cache:
            # Try to get dependencies from metadata cache
            repo_metadata = self.cache.get_repo_metadata(owner, repo, branch)
            if repo_metadata and "dependencies" in repo_metadata:
                # Need to convert back to sets since JSON doesn't support set serialization
                cached_deps = repo_metadata["dependencies"]
                dependencies = {src: set(targets) for src, targets in cached_deps.items()}
                logger.info(f"Using cached dependencies for {owner}/{repo}")
        
        # If no cached dependencies, extract them
        if not dependencies:
            # Build dependency graph using code search
            dependencies = self._extract_enhanced_dependencies(repo_files, owner, repo)
            
            # Cache the dependencies if cache is enabled
            if self.use_cache:
                # Convert sets to lists for JSON serialization
                serializable_deps = {src: list(targets) for src, targets in dependencies.items()}
                metadata = self.cache.get_repo_metadata(owner, repo, branch) or {}
                metadata["dependencies"] = serializable_deps
                self.cache.save_repo_metadata(owner, repo, metadata, branch)
        
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
            if self.mcp_client and hasattr(self.mcp_client, 'search_references'):
                # Batch processing for better performance
                batches = [list(repo_files.keys())[i:i+10] for i in range(0, len(repo_files), 10)]
                
                for batch_idx, batch in enumerate(batches):
                    logger.info(f"Processing dependency batch {batch_idx+1}/{len(batches)} ({len(batch)} files)")
                    
                    for filepath in batch:
                        # Search for references to this file
                        references = self.mcp_client.search_references(owner, repo, filepath)
                        
                        # Add reverse dependencies (files that reference this file)
                        for ref_path in references:
                            if ref_path in repo_files:
                                dependencies[ref_path].add(filepath)
            else:
                logger.warning("MCP client does not support search_references method, using basic dependencies only")
                
        except Exception as e:
            logger.warning(f"Code search-based dependency enhancement failed: {e}")
            logger.warning("Falling back to basic dependency extraction")
        
        return dependencies
    
    def analyze_repository(self, repo_files: Dict[str, str], 
                         method: AnalysisMethod = AnalysisMethod.DEPENDENCY,  # Default to enhanced dependency analysis
                         max_section_size: int = 15,
                         min_section_size: int = 2,
                         owner: str = None,
                         repo: str = None,
                         branch: str = None) -> List[Tuple[str, Dict[str, str]]]:
        """
        Analyze repository using the specified method with MCP enhancements when possible.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            method: Analysis method to use (default: DEPENDENCY for enhanced analysis)
            max_section_size: Maximum number of files in a section before subdivision
            min_section_size: Minimum number of files in a section (smaller sections will be merged)
            owner: Repository owner (required for enhanced analysis)
            repo: Repository name (required for enhanced analysis)
            branch: Repository branch
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        # Check if we have cached structure that we can use
        if self.use_cache and owner and repo and method in [AnalysisMethod.DEPENDENCY, AnalysisMethod.HYBRID]:
            # Try to get cached structure
            cached_structure = self.cache.get_repo_structure(owner, repo, branch)
            if cached_structure:
                logger.info(f"Using cached structure for {owner}/{repo}")
                
                # Verify that it contains the same files we're analyzing now
                if set(repo_files.keys()) == set(cached_structure.get("files", [])):
                    cached_sections = cached_structure.get("sections", [])
                    if cached_sections:
                        # Convert cached section data to expected format
                        sections = []
                        for section_name, file_paths in cached_sections.items():
                            section_files = {path: repo_files[path] for path in file_paths if path in repo_files}
                            if section_files:
                                sections.append((section_name, section_files))
                        
                        if sections:
                            logger.info(f"Using {len(sections)} cached sections from repository structure")
                            return sections
        
        # If we have owner and repo info, we can use enhanced dependency analysis
        if owner and repo and self.mcp_client and hasattr(self.mcp_client, 'search_references'):
            if method == AnalysisMethod.DEPENDENCY:
                logger.info(f"Using enhanced dependency analysis for {owner}/{repo}")
                sections = self.enhanced_dependency_analysis(repo_files, owner, repo, max_section_size, branch)
            elif method == AnalysisMethod.HYBRID:
                # For hybrid, start with structural and refine with enhanced dependencies
                logger.info(f"Using enhanced hybrid analysis for {owner}/{repo}")
                structural_sections = super().analyze_repository(repo_files, AnalysisMethod.STRUCTURAL, max_section_size)
                
                # Extract dependencies
                dependencies = self._extract_enhanced_dependencies(repo_files, owner, repo)
                
                # Refine large sections with dependency information
                sections = []
                for section_name, files in structural_sections:
                    if len(files) > max_section_size:
                        # Create subgraph for just this section
                        section_deps = {
                            src: {tgt for tgt in deps if tgt in files}
                            for src, deps in dependencies.items() if src in files
                        }
                        
                        # Get dependency-based subsections
                        subsections = self._group_by_dependencies(
                            files, section_deps, max_section_size
                        )
                        
                        # Rename subsections based on parent section
                        for i, (subsection_name, subsection_files) in enumerate(subsections):
                            new_name = f"{section_name}/{subsection_name}"
                            sections.append((new_name, subsection_files))
                    else:
                        sections.append((section_name, files))
            else:
                # Fall back to standard structural analysis
                sections = super().analyze_repository(repo_files, AnalysisMethod.STRUCTURAL, max_section_size)
        else:
            # Fall back to standard analysis methods
            sections = super().analyze_repository(repo_files, method, max_section_size)
        
        # Apply minimum section size if specified
        if min_section_size > 1:
            sections = self._merge_small_sections(sections, min_section_size)
        
        # Cache the sections if we have owner/repo info
        if self.use_cache and owner and repo:
            # Transform sections to a cacheable format
            cacheable_sections = {}
            for section_name, files in sections:
                cacheable_sections[section_name] = list(files.keys())
            
            # Create or update structure cache
            structure_data = self.cache.get_repo_structure(owner, repo, branch) or {}
            structure_data["sections"] = cacheable_sections
            structure_data["files"] = list(repo_files.keys())
            structure_data["section_method"] = method.name
            
            if "owner" not in structure_data:
                structure_data["owner"] = owner
                structure_data["repo"] = repo
                structure_data["branch"] = branch
            
            self.cache.update_structure_cache(owner, repo, repo_files, branch)
            
            # Update metadata with sections information
            metadata = self.cache.get_repo_metadata(owner, repo, branch) or {}
            metadata["section_count"] = len(sections)
            metadata["section_method"] = method.name
            metadata["sections"] = {name: len(files) for name, files in sections}
            self.cache.save_repo_metadata(owner, repo, metadata, branch)