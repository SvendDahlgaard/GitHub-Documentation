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
from GithubClient import GithubClient
from ClaudeSummarizer import BatchClaudeAnalyzer
from section_analyzer import SectionAnalyzer, AnalysisMethod
from ClaudeSectionAnalyzer import LLMClusterAnalyzer
from repo_cache import RepoCache

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_analysis_method(method_name: str) -> AnalysisMethod:
    """Convert string method name to AnalysisMethod enum."""
    method_map = {
        "structural": AnalysisMethod.STRUCTURAL,
        "dependency": AnalysisMethod.DEPENDENCY,
        "hybrid": AnalysisMethod.HYBRID
    }
    return method_map.get(method_name.lower(), AnalysisMethod.STRUCTURAL)

def analyze_repository(args):
    """Main function to analyze a repository by sections."""
    # Initialize cache
    cache = RepoCache() if not args.no_cache else None
    
    # First, check if we can use cached structure
    repo_structure = None
    if cache and not args.no_cache:
        logger.info(f"Checking for cached repository structure for {args.owner}/{args.repo}")
        repo_structure = cache.get_repo_structure(args.owner, args.repo, args.branch)
        if repo_structure:
            logger.info(f"Found cached repository structure with {repo_structure.get('file_count', 0)} files")
    
    # Initialize GitHub client
    try:
        github_client = GithubClient(use_cache=not args.no_cache)
        logger.info(f"Successfully initialized GitHub client")
    except Exception as e:
        logger.error(f"Failed to initialize GitHub client: {e}")
        sys.exit(1)
    
    # Initialize Claude analyzer for batch processing
    try:
        claude_analyzer = BatchClaudeAnalyzer(claude_model=args.claude_model, use_prompt_caching=not args.no_prompt_cache)
        logger.info(f"Using Claude Batch API for analysis with model: {args.claude_model}")
        logger.info(f"Prompt caching: {'enabled' if not args.no_prompt_cache else 'disabled'}")
    except Exception as e:
        logger.error(f"Failed to initialize Claude analyzer: {e}")
        sys.exit(1)
        
    # Initialize section analyzer
    if args.section_method == "llm_cluster":
        analyzer = LLMClusterAnalyzer(claude_analyzer, use_cache=not args.no_cache)
        logger.info("Using LLM-based cluster analyzer")
    else:
        analyzer = SectionAnalyzer(claude_analyzer)
        logger.info("Using standard section analyzer")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    try:
        # Get repository files - first check cache if we can use it
        repo_files = None
        if cache and not args.no_cache and not args.force_refresh:
            repo_files = cache.get_repo_files(args.owner, args.repo, args.branch)
            if repo_files:
                logger.info(f"Using {len(repo_files)} files from cache for {args.owner}/{args.repo}")
            
        # If not in cache or cache disabled, fetch from GitHub
        if not repo_files:
            logger.info(f"Fetching repository structure for {args.owner}/{args.repo}")
            repo_files = github_client.get_repository_structure(
                args.owner, 
                args.repo, 
                branch=args.branch,
                ignore_dirs=args.ignore,
                max_file_size=args.max_file_size,
                include_patterns=args.include_files,
                extensions=args.extensions,
                force_refresh=args.force_refresh,
                batch_size=args.batch_size,
                max_workers=args.max_workers
            )
        
        if not repo_files:
            logger.error("No files found or all files were filtered out")
            sys.exit(1)
            
        logger.info(f"Found {len(repo_files)} files to analyze")
        
        # Determine the section analysis method
        section_method = get_analysis_method(args.section_method)
        logger.info(f"Using {section_method.name} analysis method for sections")
        
        # Try to get repository metadata 
        if cache and not args.no_cache:
            try:
                repo_metadata = github_client.get_repository_stats(args.owner, args.repo)
                if repo_metadata:
                    logger.info(f"Retrieved repository metadata for {args.owner}/{args.repo}")
                    cache.save_repo_metadata(args.owner, args.repo, repo_metadata, args.branch)
            except Exception as e:
                logger.warning(f"Could not retrieve repository metadata: {e}")
        
        # Identify logical sections
        sections = analyzer.analyze_repository(
            repo_files, 
            method=section_method,
            max_section_size=args.max_section_size,
            min_section_size=args.min_section_size
        )
        
        logger.info(f"Identified {len(sections)} logical sections")
        
        # Save section mapping for reference
        section_map = {section: list(files.keys()) for section, files in sections}
        with open(os.path.join(args.output_dir, "sections.json"), "w") as f:
            json.dump(section_map, f, indent=2)
        
        # Analyze each section in batch
        analyses = analyze_sections_batch(sections, args.query, args.use_context, claude_analyzer, args.output_dir)
        
        # Create the index file
        index = analyzer.create_section_index(sections, analyses)
        index_path = os.path.join(args.output_dir, "index.md")
        with open(index_path, "w") as f:
            f.write(index)
            
        logger.info(f"Analysis complete. Index written to {index_path}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def analyze_sections_batch(sections, query, use_context, batch_analyzer, output_dir):
    """Analyze all sections in a batch for efficiency."""
    analyses = {}
    
    if not use_context:
        # Simple case: analyze all sections in one batch without context
        logger.info(f"Analyzing all {len(sections)} sections in a single batch")
        analyses = batch_analyzer.analyze_sections_batch(sections, query)
        
        # Save individual section analyses
        for section_name, analysis in analyses.items():
            section_filename = section_name.replace('/', '_').replace('\\', '_')
            with open(os.path.join(output_dir, f"{section_filename}.md"), "w") as f:
                f.write(f"# {section_name}\n\n")
                f.write(analysis)
    else:
        # More complex case: analyze in chunks to maintain context between groups
        # Group sections into chunks of 5-10 for efficient batching while maintaining context flow
        chunk_size = 5
        section_chunks = [sections[i:i+chunk_size] for i in range(0, len(sections), chunk_size)]
        
        context_map = {}  # Map section names to their context
        context = ""
        
        for chunk_idx, chunk in enumerate(section_chunks):
            logger.info(f"Processing batch chunk {chunk_idx+1}/{len(section_chunks)} ({len(chunk)} sections)")
            
            # Prepare context for each section in this chunk
            for section_name, _ in chunk:
                context_map[section_name] = context.strip()
            
            # Process this chunk as a batch
            chunk_results = batch_analyzer.analyze_sections_batch(chunk, query, context_map)
            analyses.update(chunk_results)
            
            # Update context for the next chunk
            for section_name, section_files in chunk:
                if section_name in chunk_results:
                    analysis = chunk_results[section_name]
                    
                    # Save individual section analysis
                    section_filename = section_name.replace('/', '_').replace('\\', '_')
                    with open(os.path.join(output_dir, f"{section_filename}.md"), "w") as f:
                        f.write(f"# {section_name}\n\n")
                        f.write(analysis)
                    
                    # Extract key points for context
                    key_points = _extract_key_points(analysis)
                    context += f"\n\nSection '{section_name}':\n{key_points}\n"
                    # Keep context from getting too large
                    context = context[-10000:] if len(context) > 10000 else context
    
    return analyses
    
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
    parser.add_argument("--claude-model", default="claude-3-5-haiku-20241022",
                      help="Claude model to use (default: claude-3-5-haiku-20241022 for cost efficiency)")
    parser.add_argument("--section-method", choices=["structural", "dependency", "hybrid", 'llm_cluster'], 
                       default="llm_cluster",
                       help="Method to use for sectioning the repository (default: llm_cluster)")
    parser.add_argument("--max-section-size", type=int, default=15,
                        help="Maximum number of files in a section before subdivision (default: 15)")
    parser.add_argument("--min-section-size", type=int, default=2,
                        help="Minimum number of files in a section - smaller sections will be merged (default: 2)")
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
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable caching of repository files")
    parser.add_argument("--no-prompt-cache", action="store_true",
                        help="Disable prompt caching for batch API")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Force refresh of repository data from GitHub, bypassing cache")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="Number of files to process in each batch during extraction (default: 20)")
    parser.add_argument("--max-workers", type=int, default=5,
                        help="Maximum number of concurrent workers for file extraction (default: 5)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    analyze_repository(args)

if __name__ == "__main__":
    main()