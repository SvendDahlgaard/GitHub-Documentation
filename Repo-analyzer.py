import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from collections import defaultdict
import logging
import re
from dotenv import load_dotenv

# Import the new direct GitHub client
from direct_github_client import DirectGitHubClient
from claude_analyzer import ClaudeAnalyzer

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
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

def analyze_repository(args):
    """Main function to analyze a repository by sections."""
    # Initialize GitHub client
    try:
        github_client = DirectGitHubClient()
        logger.info(f"Successfully initialized GitHub client")
    except Exception as e:
        logger.error(f"Failed to initialize GitHub client: {e}")
        sys.exit(1)
    
    # Initialize Claude analyzer
    try:
        if args.analysis_method == "api":
            claude_analyzer = ClaudeAnalyzer(method="api")
            logger.info("Using Claude API for analysis")
        else:
            claude_analyzer = ClaudeAnalyzer(
                method="cli", 
                claude_executable=args.claude_executable
            )
            logger.info(f"Using Claude CLI for analysis: {args.claude_executable}")
    except Exception as e:
        logger.error(f"Failed to initialize Claude analyzer: {e}")
        sys.exit(1)
        
    # Initialize section analyzer
    analyzer = SectionAnalyzer(claude_analyzer)
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    try:
        # Get repository files
        logger.info(f"Fetching repository structure for {args.owner}/{args.repo}")
        repo_files = github_client.get_repository_structure(
            args.owner, 
            args.repo, 
            branch=args.branch,
            ignore_dirs=args.ignore,
            max_file_size=args.max_file_size,
            include_patterns=args.include_files,
            extensions=args.extensions
        )
        
        if not repo_files:
            logger.error("No files found or all files were filtered out")
            sys.exit(1)
            
        logger.info(f"Found {len(repo_files)} files to analyze")
        
        # Identify logical sections
        sections = analyzer.identify_sections(repo_files)
        logger.info(f"Identified {len(sections)} logical sections")
        
        # Save section mapping for reference
        section_map = {section: list(files.keys()) for section, files in sections}
        with open(os.path.join(args.output_dir, "sections.json"), "w") as f:
            json.dump(section_map, f, indent=2)
        
        # Analyze each section, maintaining context between sections
        analyses = {}
        context = ""
        
        for i, (section_name, section_files) in enumerate(sections):
            logger.info(f"Analyzing section {i+1}/{len(sections)}: {section_name} ({len(section_files)} files)")
            
            # Analyze current section with context from previous sections
            analysis = analyzer.analyze_section(
                section_name, 
                section_files, 
                args.query, 
                context if args.use_context else None
            )
            
            analyses[section_name] = analysis
            
            # Save individual section analysis
            section_filename = section_name.replace('/', '_').replace('\\', '_')
            with open(os.path.join(args.output_dir, f"{section_filename}.md"), "w") as f:
                f.write(f"# {section_name}\n\n")
                f.write(analysis)
            
            # Update context for next section (truncated to avoid too much context)
            if args.use_context:
                # Extract key points for context
                key_points = _extract_key_points(analysis)
                context += f"\n\nSection '{section_name}':\n{key_points}\n"
                # Keep context from getting too large
                context = context[-10000:] if len(context) > 10000 else context
            
            logger.info(f"Completed analysis of section: {section_name}")
        
        # Create the index file
        index = analyzer.create_section_index(sections, analyses)
        index_path = os.path.join(args.output_dir, "index.md")
        with open(index_path, "w") as f:
            f.write(index)
            
        logger.info(f"Analysis complete. Index written to {index_path}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    
def _extract_key_points(text, max_points=5):
    """Extract key points from analysis for context."""
    # Simple extraction of sentences with key indicators
    key_sentences = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Look for sentences with indicators of importance
    indicators = ['main', 'primary', 'key', 'core', 'critical', 'essential', 'important']
    for sentence in sentences:
        if any(indicator in sentence.lower() for indicator in indicators):
            key_sentences.append(sentence)
            
        if len(key_sentences) >= max_points:
            break
            
    # If not enough key sentences found, take first few sentences
    if len(key_sentences) < 3:
        key_sentences = sentences[:5]
        
    return " ".join(key_sentences)

def main():
    parser = argparse.ArgumentParser(description="Analyze a GitHub repository by sections")
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--branch", help="Branch to analyze (default: repository's default branch)")
    parser.add_argument("--claude-executable", default="/home/svendsvupper/.npm-global/bin/claude", 
                       help="Path to Claude executable (for CLI method)")
    parser.add_argument("--analysis-method", choices=["api", "cli"], default="cli",
                       help="Method to use for Claude analysis: API or CLI (default: cli)")
    parser.add_argument("--query", help="Question to ask Claude about each section (optional)")
    parser.add_argument("--ignore", nargs="*", default=['.git', 'node_modules', '__pycache__'], 
                        help="Directories to ignore")
    parser.add_argument("--extensions", nargs="*", default=[], 
                        help="Only include files with these extensions (e.g., .py .js)")
    parser.add_argument("--max-file-size", type=int, default=500000, 
                        help="Maximum file size in bytes to include")
    parser.add_argument("--include-files", nargs="*", default=[], 
                        help="Specifically include these file patterns")
    parser.add_argument("--output-dir", default="analysis", 
                        help="Directory to output analysis files")
    parser.add_argument("--use-context", action="store_true", 
                        help="Use context from previous sections in analysis")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    analyze_repository(args)

if __name__ == "__main__":
    main()