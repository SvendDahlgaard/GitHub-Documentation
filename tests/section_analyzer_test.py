import os
import sys
import json
from dotenv import load_dotenv
sys.path.append('..')  # Add parent directory to path
from direct_github_client import DirectGitHubClient
from section_analyzer import SectionAnalyzer, AnalysisMethod

def test_section_analyzer(repo_owner, repo_name, branch=None, analysis_method="structural", 
                        min_section_size=1):
    """
    Test the section analyzer functionality by fetching a repository
    and checking if sections are created correctly.
    
    Args:
        repo_owner: Repository owner username
        repo_name: Repository name
        branch: Branch to analyze (optional)
        analysis_method: Method to use for analysis ("structural", "dependency", or "hybrid")
        min_section_size: Minimum number of files in a section
    """
    # Load environment variables
    load_dotenv()
    
    print(f"Testing section analyzer on repository: {repo_owner}/{repo_name}")
    print(f"Using analysis method: {analysis_method}")
    print(f"Minimum section size: {min_section_size}")
    
    try:
        # Initialize GitHub client
        github_client = DirectGitHubClient()
        print("✓ Successfully initialized GitHub client")
        
        # Initialize section analyzer
        section_analyzer = SectionAnalyzer()
        print("✓ Successfully initialized section analyzer")
        
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
            
        print(f"✓ Found {len(repo_files)} files to analyze")
        
        # Sample a few files to verify content
        print("\nSample files:")
        sample_count = min(3, len(repo_files))
        for i, (path, _) in enumerate(list(repo_files.items())[:sample_count]):
            print(f"  {i+1}. {path}")
        
        # Convert string method to enum
        method_map = {
            "structural": AnalysisMethod.STRUCTURAL,
            "dependency": AnalysisMethod.DEPENDENCY,
            "hybrid": AnalysisMethod.HYBRID
        }
        analysis_method_enum = method_map.get(analysis_method.lower(), AnalysisMethod.STRUCTURAL)
        
        # Identify logical sections
        print(f"\nIdentifying logical sections using {analysis_method} analysis...")
        try:
            sections = section_analyzer.analyze_repository(
                repo_files, 
                method=analysis_method_enum,
                min_section_size=min_section_size
            )
            print(f"✓ Identified {len(sections)} logical sections")
        except Exception as e:
            print(f"ERROR: Failed to analyze repository: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Print section summary
        print("\nSection summary:")
        for i, (section_name, files) in enumerate(sections):
            print(f"  {i+1}. {section_name}: {len(files)} files")
            # Print up to 3 sample files per section
            sample_files = list(files.keys())[:min(3, len(files))]
            for file in sample_files:
                print(f"     - {file}")
            if len(files) > 3:
                print(f"     - ... and {len(files) - 3} more files")
        
        # Save section mapping for reference
        output_dir = f"test_output/{analysis_method}_min{min_section_size}"
        os.makedirs(output_dir, exist_ok=True)
        section_map = {section: list(files.keys()) for section, files in sections}
        with open(os.path.join(output_dir, "test_sections.json"), "w") as f:
            json.dump(section_map, f, indent=2)
        print(f"\n✓ Section map saved to {output_dir}/test_sections.json")
        
        # Print section size statistics
        section_sizes = [len(files) for _, files in sections]
        if section_sizes:
            avg_size = sum(section_sizes) / len(section_sizes)
            min_size = min(section_sizes)
            max_size = max(section_sizes)
            print(f"\nSection size statistics:")
            print(f"  - Total sections: {len(sections)}")
            print(f"  - Average files per section: {avg_size:.2f}")
            print(f"  - Minimum files in a section: {min_size}")
            print(f"  - Maximum files in a section: {max_size}")
            print(f"  - Sections with only 1 file: {sum(1 for size in section_sizes if size == 1)}")
            
        return True
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_all_analysis_methods(repo_owner, repo_name, branch=None, min_section_size=1):
    """Run tests for all analysis methods."""
    methods = ["structural", "dependency", "hybrid"]
    results = {}
    
    print("=" * 60)
    print(f"TESTING ALL SECTION ANALYSIS METHODS ON {repo_owner}/{repo_name}")
    print(f"With minimum section size: {min_section_size}")
    print("=" * 60)
    
    for method in methods:
        print("\n" + "=" * 60)
        print(f"TESTING {method.upper()} ANALYSIS")
        print("=" * 60)
        
        success = test_section_analyzer(repo_owner, repo_name, branch, method, min_section_size)
        results[method] = success
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY OF RESULTS")
    print("=" * 60)
    
    all_success = True
    for method, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"{method.capitalize()} Analysis: {status}")
        all_success = all_success and success
    
    return all_success

def test_section_size_comparison(repo_owner, repo_name, branch=None, method="hybrid"):
    """Compare different minimum section sizes with the same analysis method."""
    min_sizes = [1, 2, 3, 5]
    results = {}
    
    print("=" * 60)
    print(f"COMPARING DIFFERENT MINIMUM SECTION SIZES ON {repo_owner}/{repo_name}")
    print(f"Using analysis method: {method}")
    print("=" * 60)
    
    for min_size in min_sizes:
        print("\n" + "=" * 60)
        print(f"TESTING WITH MINIMUM SECTION SIZE {min_size}")
        print("=" * 60)
        
        success = test_section_analyzer(repo_owner, repo_name, branch, method, min_size)
        results[min_size] = success
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY OF RESULTS")
    print("=" * 60)
    
    all_success = True
    for min_size, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"Minimum section size {min_size}: {status}")
        all_success = all_success and success
    
    return all_success

if __name__ == "__main__":
    # Default repository to test on
    default_owner = "SvendDahlgaard"
    default_repo = "GitHub-Documentation"
    
    # Allow command-line arguments to override defaults
    owner = sys.argv[1] if len(sys.argv) > 1 else default_owner
    repo = sys.argv[2] if len(sys.argv) > 2 else default_repo
    branch = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Parse additional args
    test_mode = "all"  # Default to testing all methods
    min_section_size = 1  # Default minimum section size
    
    if len(sys.argv) > 4:
        if sys.argv[4] in ["structural", "dependency", "hybrid", "all", "compare_sizes"]:
            test_mode = sys.argv[4]
        else:
            try:
                min_section_size = int(sys.argv[4])
                if min_section_size < 1:
                    min_section_size = 1
            except ValueError:
                print(f"Invalid argument: {sys.argv[4]}. Using defaults.")
    
    if len(sys.argv) > 5:
        try:
            min_section_size = int(sys.argv[5])
            if min_section_size < 1:
                min_section_size = 1
        except ValueError:
            print(f"Invalid minimum section size: {sys.argv[5]}. Using default: {min_section_size}")
    
    # Run tests based on mode
    if test_mode == "all":
        success = test_all_analysis_methods(owner, repo, branch, min_section_size)
    elif test_mode == "compare_sizes":
        success = test_section_size_comparison(owner, repo, branch, "hybrid")
    else:
        success = test_section_analyzer(owner, repo, branch, test_mode, min_section_size)
    
    if success:
        print("\nAll tests PASSED! Section analyzer is working correctly.")
    else:
        print("\nTest FAILED! Please check the error messages above.")
        sys.exit(1)