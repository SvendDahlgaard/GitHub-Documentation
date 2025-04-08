from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)

class SectionAnalyzer:
    """Analyzes a repository by sections using GitHub and Claude."""
    
    def __init__(self, claude_analyzer=None):
        self.claude_analyzer = claude_analyzer
        
    def identify_sections(self, repo_files: Dict[str, str]) -> List[Tuple[str, Dict[str, str]]]:
        """
        Automatically identify logical sections in the repository.
        Returns a list of tuples (section_name, {file_path: content})
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
                if len(dir_sections[section]) > 15 and len(parts) >= 3:
                    section = f"{parts[0]}/{parts[1]}"
            else:
                section = "root"
            
            dir_sections[section][path] = content
        
        # Further divide large sections based on file types or naming patterns
        refined_sections = []
        for section, files in dir_sections.items():
            if len(files) <= 15:
                # Keep small sections as is
                refined_sections.append((section, files))
            else:
                # For larger sections, try to subdivide
                type_sections = self._subdivide_section(section, files)
                refined_sections.extend(type_sections)
        
        # Sort sections by name for consistent output
        return sorted(refined_sections, key=lambda x: x[0])
    
    def _subdivide_section(self, section_name: str, files: Dict[str, str]) -> List[Tuple[str, Dict[str, str]]]:
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
            if len(section_files) > 15:
                # Use numeric chunking for still-large sections
                chunks = self._chunk_by_size(section_files, 10)
                for i, chunk in enumerate(chunks):
                    final_result.append((f"{name}_part{i+1}", chunk))
            else:
                final_result.append((name, section_files))
                
        return final_result
    
    def _chunk_by_size(self, files: Dict[str, str], chunk_size: int) -> List[Dict[str, str]]:
        """Split files into chunks of approximately chunk_size."""
        items = list(files.items())
        return [dict(items[i:i+chunk_size]) for i in range(0, len(items), chunk_size)]
    
    def analyze_section(self, section_name: str, section_files: Dict[str, str], 
                        query: str = None, context: str = None) -> str:
        """
        Analyze a specific section of the repository using Claude.
        
        Args:
            section_name: Name of the section
            section_files: Dictionary of file paths to contents
            query: Specific query to ask about the section
            context: Previous context to provide to Claude
            
        Returns:
            Claude's analysis of the section
        """
        if self.claude_analyzer:
            return self.claude_analyzer.analyze_code(section_name, section_files, query, context)
        else:
            return "No Claude analyzer configured. Cannot analyze this section."
    
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