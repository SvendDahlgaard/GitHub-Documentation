#!/usr/bin/env python3
"""
Test script for LLM-based clustering functionality.
This script demonstrates how the LLM clustering works and visualizes the sections it creates.
"""
import os
import sys
import json
import argparse
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.append('..')

from ClaudeBatchProcessor import BatchClaudeAnalyzer
from ClaudeSectionCluster import LLMClusterAnalyzer
from BasicSectionCluster import SectionAnalyzer, AnalysisMethod
from GithubClient import DirectGitHubClient

def visualize_sections(sections, output_dir):
    """
    Create a visualization of the sections for easier understanding.
    
    Args:
        sections: List of (section_name, files) tuples
        output_dir: Directory to save visualization files
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a markdown visualization
    md_content = "# LLM Clustering Results\n\n"
    md_content += f"Total sections created: {len(sections)}\n\n"
    
    # Create section-to-files mapping
    section_map = {}
    for section_name, files in sections:
        section_map[section_name] = list(files.keys())
    
    # Add section details to markdown
    for section_name, file_paths in section_map.items():
        md_content += f"## Section: {section_name}\n\n"
        md_content += f"Contains {len(file_paths)} files:\n\n"
        for path in sorted(file_paths):
            md_content += f"- `{path}`\n"
        md_content += "\n"
    
    # Write markdown file
    with open(os.path.join(output_dir, "llm_clustering_results.md"), "w") as f:
        f.write(md_content)
    
    # Also save the raw section map as JSON for programmatic use
    with open(os.path.join(output_dir, "llm_clustering_results.json"), "w") as f:
        json.dump(section_map, f, indent=2)
    
    print(f"Visualization saved to {output_dir}/llm_clustering_results.md")

def compare_with_other_methods(repo_files, output_dir):
    """
    Compare LLM clustering with other section methods.
    
    Args:
        repo_files: Dictionary of repository files
        output_dir: Directory to save visualization files
    """
    # Initialize a standard section analyzer
    analyzer = SectionAnalyzer()
    
    # Run each method
    methods = {
        "structural": AnalysisMethod.STRUCTURAL,
        "dependency": AnalysisMethod.DEPENDENCY,
        "hybrid": AnalysisMethod.HYBRID
    }
    
    comparison = {}
    
    for method_name, method_enum in methods.items():
        print(f"Running {method_name} analysis for comparison...")
        sections = analyzer.analyze_repository(repo_files, method=method_enum)
        section_map = {section: list(files.keys()) for section, files in sections}
        comparison[method_name] = {
            "section_count": len(sections),
            "sections": section_map
        }
    
    # Save comparison results
    with open(os.path.join(output_dir, "section_method_comparison.json"), "w") as f:
        json.dump(comparison, f, indent=2)
    
    # Create a summary markdown file
    md_content = "# Section Method Comparison\n\n"
    md_content += "| Method | Section Count | Notes |\n"
    md_content += "|--------|--------------|-------|\n"
    
    for method_name, data in comparison.items():
        md_content += f"| {method_name} | {data['section_count']} | Standard algorithm |\n"
    
    # Add LLM clustering to the table
    llm_section_count = len(json.load(open(os.path.join(output_dir, "llm_clustering_results.json"))))
    md_content += f"| llm_cluster | {llm_section_count} | Uses Claude's code understanding |\n\n"
    
    # Add details for each method
    for method_name, data in comparison.items():
        md_content += f"## {method_name.capitalize()} Method Sections\n\n"
        for section_name, files in data["sections"].items():
            md_content += f"### {section_name}\n"
            md_content += f"Contains {len(files)} files\n\n"
            # List just a sample of files to keep it manageable
            sample_size = min(5, len(files))
            for path in sorted(files)[:sample_size]:
                md_content += f"- `{path}`\n"
            if len(files) > sample_size:
                md_content += f"- ... and {len(files) - sample_size} more files\n"
            md_content += "\n"
    
    # Write comparison markdown file
    with open(os.path.join(output_dir, "section_method_comparison.md"), "w") as f:
        f.write(md_content)
    
    print(f"Comparison saved to {output_dir}/section_method_comparison.md")

def test_llm_clustering(repo_owner, repo_name, branch=None, max_section_size=15, min_section_size=2):
    """
    Test the LLM-based clustering on a repository.
    
    Args:
        repo_owner: Repository owner (username)
        repo_name: Repository name
        branch: Branch name (optional)
        max_section_size: Maximum files per section
        min_section_size: Minimum files per section
    """
    print("=== LLM Clustering Test ===")
    print(f"Testing on repository: {repo_owner}/{repo_name}")
    
    # Load environment variables
    load_dotenv()
    
    # Check for Claude API key
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        print("ERROR: No CLAUDE_API_KEY found in .env file")
        print("LLM clustering requires a Claude API key. Set it in .env file.")
        return False
    
    try:
        # Initialize GitHub client
        print("Initializing GitHub client...")
        github_client = DirectGitHubClient(use_cache=True)
        
        # Get repository files
        print(f"Fetching repository structure for {repo_owner}/{repo_name}...")
        repo_files = github_client.get_repository_structure(
            repo_owner,
            repo_name,
            branch=branch,
            ignore_dirs=['.git', 'node_modules', '__pycache__'],
            max_file_size=500000
        )
        
        if not repo_files:
            print("ERROR: No files found or all files were filtered out")
            return False
            
        print(f"Found {len(repo_files)} files to analyze")
        
        # Initialize BatchClaudeAnalyzer with Claude 3.5 Haiku (most cost-effective)
        print("Initializing BatchClaudeAnalyzer...")
        batch_analyzer = BatchClaudeAnalyzer(
            claude_model="claude-3-5-haiku-20241022",  # Most cost-effective model
            use_prompt_caching=True
        )
        
        # Initialize LLMClusterAnalyzer
        print("Initializing LLMClusterAnalyzer...")
        llm_cluster_analyzer = LLMClusterAnalyzer(
            batch_analyzer=batch_analyzer,
            use_cache=True,
            max_batch_size=10  # Process files in manageable batches
        )
        
        # Create output directory
        output_dir = "test_output/llm_clustering"
        os.makedirs(output_dir, exist_ok=True)
        
        # Run LLM-based clustering
        print("Running LLM-based clustering analysis...")
        print("This may take a few minutes as files are analyzed and clustered...")
        
        sections = llm_cluster_analyzer.analyze_repository(
            repo_files,
            max_section_size=max_section_size,
            min_section_size=min_section_size
        )
        
        print(f"Analysis complete! Created {len(sections)} logical sections.")
        
        # Visualize the results
        visualize_sections(sections, output_dir)
        
        # Compare with other methods
        print("Comparing with other sectioning methods...")
        compare_with_other_methods(repo_files, output_dir)
        
        print("\nTest completed successfully!")
        return True
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_llm_clustering_mock():
    """
    Run a mock test that doesn't make actual API calls.
    This is useful for testing the visualization without incurring costs.
    """
    print("=== LLM Clustering Test (MOCK MODE) ===")
    
    # Create some mock repository files
    repo_files = {
        "src/main.py": "print('Hello World')",
        "src/utils/helpers.py": "def add(a, b): return a + b",
        "src/utils/formatters.py": "def format_string(s): return s.strip()",
        "src/models/user.py": "class User: pass",
        "src/models/product.py": "class Product: pass",
        "src/controllers/user_controller.py": "def get_user(): pass",
        "src/controllers/product_controller.py": "def get_product(): pass",
        "src/views/user_view.py": "def render_user(): pass",
        "src/views/product_view.py": "def render_product(): pass",
        "tests/test_user.py": "def test_user(): pass",
        "tests/test_product.py": "def test_product(): pass",
        "docs/readme.md": "# Documentation",
        "config/settings.py": "DEBUG = True",
    }
    
    # Create mock sections as LLM would create them
    mock_sections = [
        ("Models", {
            "src/models/user.py": repo_files["src/models/user.py"],
            "src/models/product.py": repo_files["src/models/product.py"],
        }),
        ("Controllers", {
            "src/controllers/user_controller.py": repo_files["src/controllers/user_controller.py"],
            "src/controllers/product_controller.py": repo_files["src/controllers/product_controller.py"],
        }),
        ("Views", {
            "src/views/user_view.py": repo_files["src/views/user_view.py"],
            "src/views/product_view.py": repo_files["src/views/product_view.py"],
        }),
        ("Utilities", {
            "src/utils/helpers.py": repo_files["src/utils/helpers.py"],
            "src/utils/formatters.py": repo_files["src/utils/formatters.py"],
        }),
        ("Tests", {
            "tests/test_user.py": repo_files["tests/test_user.py"],
            "tests/test_product.py": repo_files["tests/test_product.py"],
        }),
        ("Core", {
            "src/main.py": repo_files["src/main.py"],
            "config/settings.py": repo_files["config/settings.py"],
            "docs/readme.md": repo_files["docs/readme.md"],
        }),
    ]
    
    # Create output directory
    output_dir = "test_output/llm_clustering_mock"
    os.makedirs(output_dir, exist_ok=True)
    
    # Visualize the mock sections
    visualize_sections(mock_sections, output_dir)
    
    # Create a mock comparison with other methods
    mock_comparison = {
        "structural": {
            "section_count": 4,
            "sections": {
                "src": ["src/main.py", "src/utils/helpers.py", "src/utils/formatters.py", 
                        "src/models/user.py", "src/models/product.py", 
                        "src/controllers/user_controller.py", "src/controllers/product_controller.py",
                        "src/views/user_view.py", "src/views/product_view.py"],
                "tests": ["tests/test_user.py", "tests/test_product.py"],
                "docs": ["docs/readme.md"],
                "config": ["config/settings.py"]
            }
        },
        "dependency": {
            "section_count": 3,
            "sections": {
                "module_1": ["src/models/user.py", "src/controllers/user_controller.py", 
                            "src/views/user_view.py", "tests/test_user.py"],
                "module_2": ["src/models/product.py", "src/controllers/product_controller.py", 
                            "src/views/product_view.py", "tests/test_product.py"],
                "module_3": ["src/main.py", "src/utils/helpers.py", "src/utils/formatters.py", 
                            "config/settings.py", "docs/readme.md"]
            }
        }
    }
    
    # Create comparison markdown
    md_content = "# Section Method Comparison (MOCK DATA)\n\n"
    md_content += "| Method | Section Count | Notes |\n"
    md_content += "|--------|--------------|-------|\n"
    
    for method_name, data in mock_comparison.items():
        md_content += f"| {method_name} | {data['section_count']} | Standard algorithm |\n"
    
    # Add LLM clustering to the table
    md_content += f"| llm_cluster | {len(mock_sections)} | Uses Claude's code understanding |\n\n"
    
    # Add details for each method
    for method_name, data in mock_comparison.items():
        md_content += f"## {method_name.capitalize()} Method Sections\n\n"
        for section_name, files in data["sections"].items():
            md_content += f"### {section_name}\n"
            md_content += f"Contains {len(files)} files\n\n"
            for path in sorted(files):
                md_content += f"- `{path}`\n"
            md_content += "\n"
    
    # Write comparison markdown file
    with open(os.path.join(output_dir, "section_method_comparison.md"), "w") as f:
        f.write(md_content)
    
    print(f"Mock comparison saved to {output_dir}/section_method_comparison.md")
    print("\nMock test completed successfully!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test LLM clustering functionality")
    parser.add_argument("--owner", default="SvendDahlgaard", help="Repository owner")
    parser.add_argument("--repo", default="GitHub-Documentation", help="Repository name")
    parser.add_argument("--branch", help="Branch to analyze")
    parser.add_argument("--max-section-size", type=int, default=15,
                       help="Maximum number of files in a section before subdivision")
    parser.add_argument("--min-section-size", type=int, default=2,
                       help="Minimum number of files in a section")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode without API calls")
    
    args = parser.parse_args()
    
    if args.mock:
        success = test_llm_clustering_mock()
    else:
        print("IMPORTANT: This test will make actual API calls to Claude and incur costs.")
        confirmation = input("Do you want to continue with the real test? (y/N): ")
        
        if confirmation.lower() == 'y':
            success = test_llm_clustering(
                args.owner, 
                args.repo, 
                args.branch,
                args.max_section_size,
                args.min_section_size
            )
        else:
            print("Running in mock mode instead...")
            success = test_llm_clustering_mock()
    
    sys.exit(0 if success else 1)