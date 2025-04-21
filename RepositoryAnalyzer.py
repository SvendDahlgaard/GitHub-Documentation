import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set

from GithubClient import GithubClient
from BasicSectionCluster import BasicSectionAnalyzer, AnalysisMethod
from ClaudeSectionCluster import LLMClusterAnalyzer
from RepositoryCache import RepoCache

logger = logging.getLogger(__name__)

class RepositoryAnalyzer:
    """
    Coordinates the repository analysis process, including file extraction,
    section analysis, and preparation for summarization.
    """
    
    def __init__(self, github_client, claude_summarizer, use_cache=True):
        """
        Initialize the repository analyzer.
        
        Args:
            github_client: GithubClient instance for repository interaction
            claude_summarizer: ClaudeSummarizer instance for section analysis
            use_cache: Whether to use caching for repository data
        """
        self.github_client = github_client
        self.claude_summarizer = claude_summarizer
        self.use_cache = use_cache
        self.cache = RepoCache() if use_cache else None
    
    def analyze_repository(self, args):
        """
        Main function to analyze a repository by sections.
        
        Args:
            args: Command line arguments object
            
        Returns:
            True if analysis was successful, False otherwise
        """
        # Check for cached structure if enabled
        repo_structure = None
        if self.cache is not None and not args.no_cache:
            logger.info(f"Checking for cached repository structure for {args.owner}/{args.repo}")
            repo_structure = self.cache.get_repo_structure(args.owner, args.repo, args.branch)
            if repo_structure:
                logger.info(f"Found cached repository structure with {repo_structure.get('file_count', 0)} files")
        
        # Initialize Claude analyzer for batch processing
        try:
            # Initialize section analyzer
            if args.section_method == "llm_cluster":
                analyzer = LLMClusterAnalyzer(
                    args.batch_analyzer, 
                    use_cache=not args.no_cache,
                    clustering_model=args.claude_model
                )
                logger.info("Using LLM-based cluster analyzer")
            else:
                analyzer = BasicSectionAnalyzer(
                    args.batch_analyzer, 
                    use_cache=not args.no_cache
                )
                logger.info("Using basic section analyzer")
        except Exception as e:
            logger.error(f"Failed to initialize section analyzer: {e}")
            return False
        
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        try:
            # Get repository files - first check cache if we can use it
            repo_files = None
            if self.cache and not args.no_cache and not args.force_refresh:
                repo_files = self.cache.get_repo_files(args.owner, args.repo, args.branch)
                if repo_files:
                    logger.info(f"Using {len(repo_files)} files from cache for {args.owner}/{args.repo}")
                
            # If not in cache or cache disabled, fetch from GitHub
            if not repo_files:
                logger.info(f"Fetching repository structure for {args.owner}/{args.repo}")
                repo_files = self.github_client.get_repository_structure(
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
                return False
                
            logger.info(f"Found {len(repo_files)} files to analyze")
            
            # Determine the section analysis method if using BasicSectionAnalyzer
            section_method = None
            if not isinstance(analyzer, LLMClusterAnalyzer) and args.section_method != "llm_cluster":
                section_method = self._get_analysis_method(args.section_method)
                logger.info(f"Using {section_method.name} analysis method for basic section analyzer")
            
            # Try to get repository metadata 
            if self.cache and not args.no_cache:
                try:
                    repo_metadata = self.github_client.get_repository_stats(args.owner, args.repo)
                    if repo_metadata:
                        logger.info(f"Retrieved repository metadata for {args.owner}/{args.repo}")
                        self.cache.save_repo_metadata(args.owner, args.repo, repo_metadata, args.branch)
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
            analyses = self.claude_summarizer.create_summaries_batch(
                sections, 
                args.query, 
                args.use_context
            )
            
            # Create the index file
            index = analyzer.create_section_index(sections, analyses)
            index_path = os.path.join(args.output_dir, "index.md")
            with open(index_path, "w") as f:
                f.write(index)
                
            logger.info(f"Analysis complete. Index written to {index_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_analysis_method(self, method_name: str) -> AnalysisMethod:
        """Convert string method name to AnalysisMethod enum."""
        method_map = {
            "structural": AnalysisMethod.STRUCTURAL,
            "dependency": AnalysisMethod.DEPENDENCY,
            "hybrid": AnalysisMethod.HYBRID
        }
        return method_map.get(method_name.lower(), AnalysisMethod.STRUCTURAL)