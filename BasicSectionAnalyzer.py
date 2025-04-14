from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional, Any
from collections import defaultdict
import re
import logging
import networkx as nx
from enum import Enum, auto

logger = logging.getLogger(__name__)

class AnalysisMethod(Enum):
    """Enum for different section analysis methods."""
    STRUCTURAL = auto()  # Original directory-based method
    DEPENDENCY = auto()  # Dependency-based analysis
    HYBRID = auto()      # Combined approach

class BasicSectionAnalyzer:
    """
    Analyzes a repository using algorithmic methods to divide it into logical sections.
    This class provides traditional approaches like structural and dependency-based analysis.
    """
    
    def __init__(self, claude_analyzer=None, use_cache=True):
        """
        Initialize the basic section analyzer.
        
        Args:
            claude_analyzer: The Claude analyzer for code analysis
            use_cache: Whether to use caching for results
        """
        self.claude_analyzer = claude_analyzer
        self.use_cache = use_cache
    
    def analyze_repository(self, repo_files: Dict[str, str], 
                         method: AnalysisMethod = AnalysisMethod.STRUCTURAL,
                         max_section_size: int = 15,
                         min_section_size: int = 2) -> List[Tuple[str, Dict[str, str]]]:
        """
        Analyze repository using the specified method.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            method: Analysis method to use
            max_section_size: Maximum number of files in a section before subdivision
            min_section_size: Minimum number of files in a section (smaller sections will be merged)
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        if method == AnalysisMethod.STRUCTURAL:
            sections = self.structural_analysis(repo_files, max_section_size)
        elif method == AnalysisMethod.DEPENDENCY:
            sections = self.dependency_analysis(repo_files, max_section_size)
        elif method == AnalysisMethod.HYBRID:
            sections = self.hybrid_analysis(repo_files, max_section_size)
        else:
            logger.warning(f"Unknown analysis method: {method}. Using structural analysis.")
            sections = self.structural_analysis(repo_files, max_section_size)
        
        # Apply minimum section size if specified
        if min_section_size > 1:
            sections = self._merge_small_sections(sections, min_section_size)
            
        return sections
    
    def _merge_small_sections(self, sections: List[Tuple[str, Dict[str, str]]], 
                           min_size: int) -> List[Tuple[str, Dict[str, str]]]:
        """
        Merge sections that are smaller than the minimum size.
        
        Strategy:
        1. Keep all sections that meet the minimum size
        2. Group small sections by their parent directory/category
        3. Merge small sections within the same group
        4. If merged sections are still too small, add them to a "miscellaneous" section
        
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
        
    def structural_analysis(self, repo_files: Dict[str, str], 
                          max_section_size: int = 15) -> List[Tuple[str, Dict[str, str]]]:
        """
        Automatically identify logical sections based on directory structure.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            max_section_size: Maximum number of files in a section before subdivision
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        # Group files by directory structure first
        dir_sections = defaultdict(dict)
        
        for path, content in repo_files.items():
            # Get the top-level directory or second-level if first is too broad
            parts = Path(path).parts
            if len(parts) >= 2:
                # Use first directory level
                section = parts[0]
                
                # If there are too many files in this top level, use two levels
                if len(dir_sections[section]) > max_section_size and len(parts) >= 3:
                    section = f"{parts[0]}/{parts[1]}"
            else:
                section = "root"
            
            dir_sections[section][path] = content
        
        # Further divide large sections based on file types or naming patterns
        refined_sections = []
        for section, files in dir_sections.items():
            if len(files) <= max_section_size:
                # Keep small sections as is
                refined_sections.append((section, files))
            else:
                # For larger sections, try to subdivide
                type_sections = self._subdivide_section(section, files, max_section_size)
                refined_sections.extend(type_sections)
        
        # Sort sections by name for consistent output
        return sorted(refined_sections, key=lambda x: x[0])
    
    def dependency_analysis(self, repo_files: Dict[str, str], 
                          max_section_size: int = 15) -> List[Tuple[str, Dict[str, str]]]:
        """
        Group files based on dependencies and imports between them.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            max_section_size: Maximum number of files in a section
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        # First, extract import relationships between files
        dependencies = self._extract_dependencies(repo_files)
        
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
        components = list(nx.strongly_connected_components(G))
        
        # If networkx is unavailable, fall back to simple grouping
        if not components:
            logger.warning("NetworkX strongly connected components failed, using simple grouping")
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
    
    def hybrid_analysis(self, repo_files: Dict[str, str], 
                       max_section_size: int = 15) -> List[Tuple[str, Dict[str, str]]]:
        """
        Combine structural and dependency-based analysis for better results.
        
        First groups files by directory structure, then refines large sections
        using dependency analysis.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            max_section_size: Maximum number of files in a section
            
        Returns:
            List of tuples (section_name, {file_path: content})
        """
        # Start with directory-based grouping
        dir_sections = defaultdict(dict)
        
        for path, content in repo_files.items():
            # Get the top-level directory
            parts = Path(path).parts
            if len(parts) >= 1:
                section = parts[0]
            else:
                section = "root"
            
            dir_sections[section][path] = content
        
        # Extract dependencies for potential refinement
        dependencies = self._extract_dependencies(repo_files)
        
        # Refine sections based on size and dependencies
        refined_sections = []
        for section_name, files in dir_sections.items():
            if len(files) <= max_section_size:
                # Keep small sections as is
                refined_sections.append((section_name, files))
            else:
                # Try to use dependency analysis for large sections
                try:
                    # Create subgraph for just this section
                    section_deps = {
                        src: {tgt for tgt in deps if tgt in files}
                        for src, deps in dependencies.items() if src in files
                    }
                    
                    # Get dependency-based subsections
                    subsections = self._group_by_dependencies(
                        files, section_deps, max_section_size
                    )
                    
                    # Name subsections based on parent section
                    renamed_subsections = []
                    for i, (subsection_name, subsection_files) in enumerate(subsections):
                        # Use original subsection name if it's more descriptive than a number
                        if re.match(r'^(module|component|group)_\d+$', subsection_name):
                            new_name = f"{section_name}/subsection_{i+1}"
                        else:
                            new_name = f"{section_name}/{subsection_name}"
                        renamed_subsections.append((new_name, subsection_files))
                    
                    refined_sections.extend(renamed_subsections)
                except Exception as e:
                    logger.warning(f"Dependency analysis failed for {section_name}: {e}")
                    # Fall back to pattern-based subdivision
                    pattern_subsections = self._subdivide_section(section_name, files, max_section_size)
                    refined_sections.extend(pattern_subsections)
        
        return sorted(refined_sections, key=lambda x: x[0])
    
    def _extract_dependencies(self, repo_files: Dict[str, str]) -> Dict[str, Set[str]]:
        """
        Extract import dependencies between files.
        
        Args:
            repo_files: Dictionary mapping file paths to contents
            
        Returns:
            Dictionary mapping file paths to sets of imported file paths
        """
        # Map of file paths to sets of imported file paths
        dependencies = defaultdict(set)
        
        # Map file paths to their module names (for resolving imports)
        path_to_module = {}
        for path in repo_files.keys():
            if path.endswith('.py'):
                # Convert path to potential module name
                parts = Path(path).with_suffix('').parts
                # Handle __init__.py files
                if parts[-1] == '__init__':
                    module_name = '.'.join(parts[:-1]) if len(parts) > 1 else ''
                else:
                    module_name = '.'.join(parts)
                path_to_module[module_name] = path
        
        # Extract Python imports
        python_import_patterns = [
            # from X import Y
            r'from\s+([\w.]+)\s+import\s+[\w, \t\n]+',
            # import X
            r'import\s+([\w.]+)',
            # import X as Y
            r'import\s+([\w.]+)\s+as\s+\w+',
        ]
        
        # Look for imports in Python files
        for path, content in repo_files.items():
            if path.endswith('.py'):
                for pattern in python_import_patterns:
                    for match in re.finditer(pattern, content):
                        imported_module = match.group(1)
                        
                        # Skip standard library imports
                        if imported_module.split('.')[0] in {'os', 'sys', 'time', 'datetime', 
                                                          'json', 're', 'math', 'random',
                                                          'collections', 'typing', 'pathlib'}:
                            continue
                        
                        # Try to resolve the import to a file path
                        resolved_paths = set()
                        
                        # Try direct match
                        if imported_module in path_to_module:
                            resolved_paths.add(path_to_module[imported_module])
                        
                        # Try parent modules (for from X.Y import Z)
                        parts = imported_module.split('.')
                        for i in range(1, len(parts)):
                            parent = '.'.join(parts[:-i])
                            if parent in path_to_module:
                                resolved_paths.add(path_to_module[parent])
                        
                        # Add dependencies
                        for resolved_path in resolved_paths:
                            if resolved_path != path:  # Avoid self-references
                                dependencies[path].add(resolved_path)
        
        return dependencies
    
    def _fallback_dependency_grouping(self, repo_files: Dict[str, str], 
                                    dependencies: Dict[str, Set[str]],
                                    max_section_size: int) -> List[Tuple[str, Dict[str, str]]]:
        """Fallback method for when network analysis is unavailable."""
        # Group files by their directory first
        dir_groups = defaultdict(list)
        for path in repo_files:
            dir_name = str(Path(path).parent)
            dir_groups[dir_name].append(path)
        
        # Further group by shared dependencies
        sections = []
        for dir_name, paths in dir_groups.items():
            if len(paths) <= max_section_size:
                # Small enough to keep as one group
                section_files = {p: repo_files[p] for p in paths}
                sections.append((f"dir_{dir_name}", section_files))
            else:
                # Create an undirected dependency graph
                shared_deps = defaultdict(set)
                for i, path1 in enumerate(paths):
                    for path2 in paths[i+1:]:
                        # Check if they share dependencies
                        deps1 = dependencies.get(path1, set())
                        deps2 = dependencies.get(path2, set())
                        # Also check for direct dependencies
                        if path2 in deps1 or path1 in deps2 or deps1.intersection(deps2):
                            shared_deps[path1].add(path2)
                            shared_deps[path2].add(path1)
                
                # Greedy clustering
                assigned = set()
                for path in sorted(paths, key=lambda p: len(shared_deps.get(p, set())), reverse=True):
                    if path in assigned:
                        continue
                    
                    # Start a new group with this file
                    group = {path}
                    assigned.add(path)
                    
                    # Add connected files
                    to_check = list(shared_deps.get(path, set()) - assigned)
                    while to_check and len(group) < max_section_size:
                        next_file = to_check.pop(0)
                        if next_file not in assigned:
                            group.add(next_file)
                            assigned.add(next_file)
                            to_check.extend(p for p in shared_deps.get(next_file, set()) 
                                          if p not in assigned and p not in to_check)
                    
                    # Add group as a section
                    section_files = {p: repo_files[p] for p in group}
                    name_base = Path(list(group)[0]).stem.replace('.', '_')
                    sections.append((f"{dir_name}_{name_base}_group", section_files))
        
        return sections
    
    def _group_by_dependencies(self, files: Dict[str, str], 
                             dependencies: Dict[str, Set[str]],
                             max_section_size: int) -> List[Tuple[str, Dict[str, str]]]:
        """
        Group files by their dependencies using community detection.
        
        Args:
            files: Dictionary of files to group
            dependencies: Map of file paths to their dependencies
            max_section_size: Maximum size of a section
            
        Returns:
            List of section tuples
        """
        try:
            import networkx as nx
            
            # Create an undirected graph of dependencies
            G = nx.Graph()
            
            # Add all files as nodes
            for path in files:
                G.add_node(path)
            
            # Add edges for dependencies (both directions)
            for source, targets in dependencies.items():
                if source in files:
                    for target in targets:
                        if target in files:
                            G.add_edge(source, target)
            
            # Find communities/modules using Louvain method
            try:
                # Try with python-louvain if available
                from community import best_partition
                partition = best_partition(G)
                communities = defaultdict(list)
                for node, community_id in partition.items():
                    communities[community_id].append(node)
                
                # Convert to list of lists
                community_groups = list(communities.values())
            except ImportError:
                # Fall back to networkx's connected_components
                logger.warning("python-louvain not available, using connected components")
                community_groups = list(nx.connected_components(G))
            
            # Create sections from communities
            sections = []
            unassigned = set(files.keys())
            
            for i, community in enumerate(community_groups):
                community_files = {path: files[path] for path in community if path in files}
                if community_files:
                    # Find common prefix if possible
                    prefix = self._find_common_prefix(community_files.keys())
                    section_name = f"{prefix}_module_{i+1}" if prefix else f"module_{i+1}"
                    
                    if len(community_files) > max_section_size:
                        # Subdivide large communities
                        subdivisions = self._subdivide_section(section_name, community_files, max_section_size)
                        sections.extend(subdivisions)
                    else:
                        sections.append((section_name, community_files))
                    
                    unassigned -= community_files.keys()
            
            # Handle unassigned files
            if unassigned:
                leftover_files = {path: files[path] for path in unassigned}
                # Group by extension
                by_extension = defaultdict(dict)
                for path, content in leftover_files.items():
                    ext = Path(path).suffix.lower() or ".unknown"
                    by_extension[ext][path] = content
                
                for ext, ext_files in by_extension.items():
                    if len(ext_files) > max_section_size:
                        chunks = self._chunk_by_size(ext_files, max_section_size // 2)
                        for i, chunk in enumerate(chunks):
                            sections.append((f"uncategorized_{ext[1:]}_files_part{i+1}", chunk))
                    else:
                        sections.append((f"uncategorized_{ext[1:]}_files", ext_files))
            
            return sections
            
        except (ImportError, Exception) as e:
            logger.warning(f"NetworkX community detection failed: {e}")
            return self._fallback_dependency_grouping(files, dependencies, max_section_size)
    
    def _find_common_prefix(self, paths: List[str]) -> str:
        """Find common directory prefix among paths."""
        if not paths:
            return ""
            
        # Convert to Path objects and get parts
        path_parts = [Path(p).parts for p in paths]
        
        # Find common prefix length
        min_len = min(len(parts) for parts in path_parts)
        prefix_parts = []
        
        for i in range(min_len):
            if all(parts[i] == path_parts[0][i] for parts in path_parts):
                prefix_parts.append(path_parts[0][i])
            else:
                break
        
        if not prefix_parts:
            return ""
            
        # Return the common prefix
        return prefix_parts[-1]  # Just use the last directory in common
    
    def _subdivide_section(self, section_name: str, files: Dict[str, str], 
                         max_section_size: int = 15) -> List[Tuple[str, Dict[str, str]]]:
        """Subdivide a large section into smaller ones based on patterns."""
        # Try to identify logical groups by file patterns
        groups = defaultdict(dict)
        
        # Track files that have been assigned to a group
        assigned = set()
        
        # Common patterns in SDKs: APIs, models, utilities, tests, etc.
        patterns = [
            (r'api|client', 'apis'),
            (r'model|schema|type', 'models'),
            (r'util|helper|common', 'utilities'),
            (r'test|spec', 'tests'),
            (r'config|settings', 'configuration'),
            (r'exception|error', 'errors'),
            (r'auth|security', 'authentication'),
            (r'logger|logging', 'logging'),
            (r'db|database|storage', 'storage'),
            (r'http|request', 'networking'),
            (r'ui|view', 'ui'),
            (r'transform|converter', 'transforms'),
            (r'mock|fake|stub', 'mocks'),
        ]
        
        # First pass: check for specific patterns
        for path, content in files.items():
            file_name = Path(path).name.lower()
            
            # Try to match against known patterns
            for pattern, group in patterns:
                if re.search(pattern, file_name, re.IGNORECASE):
                    subsection = f"{section_name}/{group}"
                    groups[subsection][path] = content
                    assigned.add(path)
                    break
        
        # Second pass: group by file extension for remaining files
        for path, content in files.items():
            if path in assigned:
                continue
                
            ext = Path(path).suffix.lower() or "unknown"
            if ext.startswith('.'):
                ext = ext[1:]  # Remove leading dot
                
            subsection = f"{section_name}/{ext}_files"
            groups[subsection][path] = content
        
        # Convert defaultdict to list of tuples
        result = [(name, files) for name, files in groups.items()]
        
        # Further subdivide if any section is still too large
        final_result = []
        for name, section_files in result:
            if len(section_files) > max_section_size:
                # Use numeric chunking for still-large sections
                chunks = self._chunk_by_size(section_files, max_section_size // 2 + 1)
                for i, chunk in enumerate(chunks):
                    final_result.append((f"{name}_part{i+1}", chunk))
            else:
                final_result.append((name, section_files))
                
        return final_result
    
    def _chunk_by_size(self, files: Dict[str, str], chunk_size: int) -> List[Dict[str, str]]:
        """Split files into chunks of approximately chunk_size."""
        items = list(files.items())
        return [dict(items[i:i+chunk_size]) for i in range(0, len(items), chunk_size)]
    
    def create_section_index(self, sections: List[Tuple[str, Dict[str, str]]], analyses: Dict[str, str]) -> str:
        """Create an index/directory of all analyzed sections with links."""
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