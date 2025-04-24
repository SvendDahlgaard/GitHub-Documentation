import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from datetime import datetime

from GithubClient import GithubClient
from ClusteringAdhoc import BasicSectionAnalyzer, AnalysisMethod
from ClusteringClaude import LLMClusterAnalyzer
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
        
        # Create repository-specific output directory
        repo_output_dir = self._create_repo_output_dir(args.owner, args.repo, args.output_dir)
        
        # Update the summarizer's output directory to the repository-specific one
        self.claude_summarizer.set_output_directory(repo_output_dir)
        
        try:
            # Get repository files - first check cache if we can use it
            repo_files = None
            if self.cache and not args.no_cache and not args.force_refresh:
                repo_files = self.cache.get_repo_files(args.owner, args.repo)
                if repo_files:
                    logger.info(f"Using {len(repo_files)} files from cache for {args.owner}/{args.repo}")
                
            # If not in cache or cache disabled, fetch from GitHub
            if not repo_files:
                logger.info(f"Fetching repository structure for {args.owner}/{args.repo}")
                repo_files = self.github_client.get_repository_files(
                    args.owner, 
                    args.repo, 
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
            
            # Identify logical sections
            sections = analyzer.cluster_repository(
                repo_files, 
                method=section_method,
                max_section_size=args.max_section_size,
                min_section_size=args.min_section_size,
                auto_filter = args.auto_filter 
            )
            
            logger.info(f"Identified {len(sections)} logical sections")
            
            # Save section mapping for reference
            section_map = {section: list(files.keys()) for section, files in sections}
            with open(os.path.join(repo_output_dir, "sections.json"), "w") as f:
                json.dump(section_map, f, indent=2)
            
            # Summarize each section
            analyses = self.claude_summarizer.create_section_summaries(
                sections, 
                args.query, 
                args.use_context,
                model=args.claude_model
            )
            
            # Create the index file with a unique name
            index = analyzer.create_section_index(sections, analyses)
            index_path = self._create_unique_index_path(repo_output_dir, args.owner, args.repo)
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
    
    def _create_repo_output_dir(self, owner: str, repo: str, base_output_dir: str) -> str:
        """
        Create a repository-specific output directory.
        
        Args:
            owner: Repository owner
            repo: Repository name
            base_output_dir: Base output directory
            
        Returns:
            Path to the repository-specific output directory
        """
        # Create a unique directory for this repository
        repo_dir = os.path.join(base_output_dir, f"{owner}_{repo}")
        os.makedirs(repo_dir, exist_ok=True)
        return repo_dir
    
    def _create_unique_index_path(self, repo_output_dir: str, owner: str, repo: str) -> str:
        """
        Create a unique path for the index file based on repository and timestamp.
        
        Args:
            repo_output_dir: Repository output directory
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Path to the unique index file
        """
        # Create a timestamp string
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a unique filename for the index
        index_filename = f"{owner}_{repo}_{timestamp}_index.md"
        
        return os.path.join(repo_output_dir, index_filename)