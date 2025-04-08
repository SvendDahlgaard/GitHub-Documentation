import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
import logging
import re
from dotenv import load_dotenv

# Import modules
from direct_github_client import DirectGitHubClient
from claude_analyzer import ClaudeAnalyzer
from section_analyzer import SectionAnalyzer

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

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
    parser.add_argument("--claude-executable", default="claude", 
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