import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Import modules
from GithubClient import GithubClient
from ClaudeBatchProcessor import BatchClaudeAnalyzer
from RepositoryAnalyzer import RepositoryAnalyzer
from ClaudeSummarizer import ClaudeSummarizer

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Analyze a GitHub repository by sections")
    parser.add_argument("--owner", default = "SvendDahlgaard", help="GitHub repository owner")
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
                        help="Base directory for output files (repository-specific directories will be created)")
    parser.add_argument("--use-context", default=True, 
                        help="Use context from previous sections in analysis")
    parser.add_argument("--no-cache", default=False,
                        help="Disable caching of repository files")
    parser.add_argument("--prompt-cache", default=True,
                        help="Disable prompt caching for batch API")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Force refresh of repository data from GitHub, bypassing cache")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="Number of files to process in each batch during extraction (default: 20)")
    parser.add_argument("--max-workers", type=int, default=5,
                        help="Maximum number of concurrent workers for file extraction (default: 5)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose logging")
    parser.add_argument("--auto-filter", default=True,
                        help="Determines whether to use automatic filtering of less important files")
    parser.add_argument("--batch", action="store_true",
                   help="Disable batch processing and use direct API calls")
    
    return parser.parse_args()

def main():
    """Main entry point for the application."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Initialize GitHub client
        github_client = GithubClient(use_cache=not args.no_cache)
        logger.info(f"Successfully initialized GitHub client")
        
        # Initialize Claude analyzer for batch processing
        batch_analyzer = BatchClaudeAnalyzer(
            use_prompt_caching= args.prompt_cache
        )
        logger.info(f"Using Claude Batch API for analysis with model: {args.claude_model}")
        logger.info(f"Prompt caching: {'enabled' if args.prompt_cache else 'disabled'}")
        
        # Make the batch analyzer available to the args for use in RepositoryAnalyzer
        args.batch_analyzer = batch_analyzer
        
        # Create base output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Initialize Claude summarizer - output directory for sections will be set in RepositoryAnalyzer
        claude_summarizer = ClaudeSummarizer(
            batch_analyzer=batch_analyzer,
            output_dir=args.output_dir  # This will be refined in RepositoryAnalyzer
        )
        
        # Initialize repository analyzer
        repo_analyzer = RepositoryAnalyzer(
            github_client=github_client,
            claude_summarizer=claude_summarizer,
            use_cache=not args.no_cache
        )
        
        # Perform the analysis
        success = repo_analyzer.analyze_repository(args)
        
        if success:
            repo_output_dir = os.path.join(args.output_dir, f"{args.owner}_{args.repo}")
            logger.info(f"Repository analysis completed successfully")
            logger.info(f"Output files are in: {repo_output_dir}")
            return 0
        else:
            logger.error("Repository analysis failed")
            return 1
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())