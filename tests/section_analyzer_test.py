import os
import sys
import json
from dotenv import load_dotenv
sys.path.append('..')  # Add parent directory to path
from direct_github_client import DirectGitHubClient
from section_analyzer import SectionAnalyzer

def test_section_analyzer(repo_owner, repo_name, branch=None):
    """
    Test the section analyzer functionality by fetching a repository
    and checking if sections are created correctly.
    
    Args:
        repo_owner: Repository owner username
        repo_name: Repository name
        branch: Branch to analyze (optional)
    """
    # Load environment variables
    load_dotenv()
    
    print(f"Testing section analyzer on repository: {repo_owner}/{repo_name}")
    
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
        
        # Identify logical sections
        print("\nIdentifying logical sections...")
        sections = section_analyzer.identify_sections(repo_files)
        print(f"✓ Identified {len(sections)} logical sections")
        
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
        output_dir = "test_output"
        os.makedirs(output_dir, exist_ok=True)
        section_map = {section: list(files.keys()) for section, files in sections}
        with open(os.path.join(output_dir, "test_sections.json"), "w") as f:
            json.dump(section_map, f, indent=2)
        print(f"\n✓ Section map saved to {output_dir}/test_sections.json")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Default repository to test on
    default_owner = "SvendDahlgaard"
    default_repo = "GitHub-Documentation"
    
    # Allow command-line arguments to override defaults
    owner = sys.argv[1] if len(sys.argv) > 1 else default_owner
    repo = sys.argv[2] if len(sys.argv) > 2 else default_repo
    branch = sys.argv[3] if len(sys.argv) > 3 else None
    
    success = test_section_analyzer(owner, repo, branch)
    
    if success:
        print("\nAll tests PASSED! Section analyzer is working correctly.")
    else:
        print("\nTest FAILED! Please check the error messages above.")
        sys.exit(1)