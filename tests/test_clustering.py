import os
import sys
import json
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the required modules
from ClusteringAdhoc import BasicSectionAnalyzer, AnalysisMethod
from ClusteringClaude import LLMClusterAnalyzer
from ClaudeBatchProcessor import BatchClaudeAnalyzer
from BaseClusteringAbstractClass import BaseRepositoryAnalyzer
from GithubClient import GithubClient

# Load environment variables
load_dotenv()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test repository clustering methods")
    parser.add_argument("--repo", help="GitHub repository name (e.g., 'GitHub-Documentation')")
    parser.add_argument("--owner", default="SvendDahlgaard", help="GitHub repository owner")
    parser.add_argument("--output-dir", default="test_output", help="Directory for output files")
    parser.add_argument("--methods", choices=["structural", "dependency", "hybrid", "all", "all_with_llm"], 
                        default="all", help="Methods to test: individual, all (excluding LLM), or all_with_llm")
    parser.add_argument("--no-cache", action="store_true", help="Bypass cache when fetching from GitHub")
    parser.add_argument("--max-file-size", type=int, default=500000, 
                        help="Maximum file size in bytes to include")
    
    return parser.parse_args()

def main():
    """
    Main function to run clustering tests.
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Create output directory for test results
    test_output_dir = args.output_dir
    os.makedirs(test_output_dir, exist_ok=True)
    
    logger.info(f"Test results will be saved to: {os.path.abspath(test_output_dir)}")
    
    # Initialize GitHub client (handles caching internally)
    github_client = GithubClient(use_cache=not args.no_cache)
    
    # Load repository files
    repo_name = args.repo if args.repo else "GitHub-Documentation"
    owner = args.owner
    
    logger.info(f"Loading repository: {owner}/{repo_name}")
    repo_files = github_client.get_repository_files(
        owner,
        repo_name,
        max_file_size=args.max_file_size,
        force_refresh=args.no_cache
    )
    
    if not repo_files:
        logger.error("No repository files loaded. Exiting.")
        return
    
    logger.info(f"Loaded {len(repo_files)} files from repository")
    
    # Save the list of files for reference
    with open(os.path.join(test_output_dir, f"{repo_name}_files.json"), "w") as f:
        json.dump(list(repo_files.keys()), f, indent=2)
    
    # Determine which methods to test
    methods_to_test = []
    test_llm = False
    
    if args.methods == "all":
        methods_to_test = ["structural", "dependency", "hybrid"]
    elif args.methods == "all_with_llm":
        methods_to_test = ["structural", "dependency", "hybrid"]
        test_llm = True
    else:
        methods_to_test = [args.methods]
    
    # Initialize the BasicSectionAnalyzer
    basic_analyzer = BasicSectionAnalyzer()
    
    # Test each requested method
    results = {}
    
    # Method mapping
    method_map = {
        "structural": AnalysisMethod.STRUCTURAL,
        "dependency": AnalysisMethod.DEPENDENCY,
        "hybrid": AnalysisMethod.HYBRID
    }
    
    # Test BasicSectionAnalyzer methods
    for method_name in methods_to_test:
        method = method_map.get(method_name)
        if not method:
            continue
            
        logger.info(f"Testing {method_name} clustering method...")
        
        # Run the analyzer with auto_filter enabled
        sections = basic_analyzer.cluster_repository(
            repo_files.copy(),  # Use a copy to avoid modifying the original
            method=method,
            max_section_size=15,
            min_section_size=2,
            auto_filter=True
        )
        
        # Save results
        section_data = {}
        for section_name, files in sections:
            section_data[section_name] = list(files.keys())
        
        results[f"basic_{method_name}"] = {
            "section_count": len(sections),
            "sections": section_data
        }
        
        # Save to JSON file
        output_file = os.path.join(test_output_dir, f"{repo_name}_{method_name}_sections.json")
        with open(output_file, "w") as f:
            json.dump(results[f"basic_{method_name}"], f, indent=2)
            
        logger.info(f"Created {len(sections)} sections using {method_name} method")
    
    # Test LLM clustering if requested
    if test_llm:
        logger.info("Testing LLM-based clustering method...")
        
        # Check if Claude API key is available
        claude_api_key = os.getenv("CLAUDE_API_KEY")
        if not claude_api_key:
            logger.warning("No Claude API key found. LLM clustering test will be skipped.")
        else:
            # Initialize the batch analyzer
            batch_analyzer = BatchClaudeAnalyzer()
            
            # Initialize the LLM analyzer
            llm_analyzer = LLMClusterAnalyzer(
                batch_analyzer=batch_analyzer,
                max_batch_size=5
            )
            
            # Run the LLM analyzer
            sections = llm_analyzer.cluster_repository(
                repo_files.copy(),  # Use a copy to avoid modifying the original
                max_section_size=15,
                min_section_size=2,
                auto_filter=True
            )
            
            # Save results
            section_data = {}
            for section_name, files in sections:
                section_data[section_name] = list(files.keys())
            
            results["llm"] = {
                "section_count": len(sections),
                "sections": section_data
            }
            
            # Save to JSON file
            output_file = os.path.join(test_output_dir, f"{repo_name}_llm_sections.json")
            with open(output_file, "w") as f:
                json.dump(results["llm"], f, indent=2)
                
            logger.info(f"Created {len(sections)} sections using LLM-based clustering")
    
    # Create and save summary
    summary = {
        "repository": f"{owner}/{repo_name}",
        "total_files": len(repo_files),
        "methods": {k: v["section_count"] for k, v in results.items()}
    }
    
    # Save summary
    summary_file = os.path.join(test_output_dir, f"{repo_name}_summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    # Print summary to console
    logger.info("\n" + "="*50)
    logger.info(f"CLUSTERING SUMMARY FOR: {owner}/{repo_name}")
    logger.info(f"Total files analyzed: {len(repo_files)}")
    logger.info("-"*50)
    
    for method, data in results.items():
        logger.info(f"{method}: {data['section_count']} sections")
    
    logger.info("-"*50)
    logger.info(f"Results saved to: {os.path.abspath(test_output_dir)}")
    logger.info("="*50)

if __name__ == "__main__":
    main()