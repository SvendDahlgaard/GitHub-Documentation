import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append('..')

# Import required modules
# To this
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from GithubClient import GithubClient
from ClusteringAdhoc import BasicSectionAnalyzer, AnalysisMethod
from ClaudeBatchProcessor import BatchClaudeAnalyzer

# Load environment variables
load_dotenv()

def test_github_connection():
    """
    Test GitHub API connection and token validity.
    This is the most basic test to ensure GitHub access works.
    """
    print("\n==== Testing GitHub API Connection ====")
    
    # Check for GitHub token
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ ERROR: No GitHub token found in .env file")
        return False
    
    try:
        # Initialize GitHub client
        github_client = GithubClient(use_cache=False)  # Don't use cache for the test
        print("✅ Successfully initialized GitHub client")
        
        # Test listing a simple repository
        test_owner = "SvendDahlgaard"  # Use your username
        test_repo = "GitHub-Documentation"  # Use a small test repo
        
        files = github_client.list_repository_files(test_owner, test_repo, "")
        if files:
            print(f"✅ Successfully listed {len(files)} files/directories in {test_owner}/{test_repo}")
            return True
        else:
            print(f"❌ Failed to list files in {test_owner}/{test_repo}")
            return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_basic_section_analyzer():
    """
    Test the basic section analyzer functionality.
    This tests the core logic of dividing a codebase into sections.
    """
    print("\n==== Testing Basic Section Analyzer ====")
    
    # Create a simple test repository
    test_files = {
        "src/main.py": "print('Hello world')",
        "src/utils/helpers.py": "def add(a, b): return a + b",
        "src/utils/constants.py": "PI = 3.14159",
        "tests/test_main.py": "def test_main(): pass",
        "README.md": "# Test Repository"
    }
    
    try:
        # Initialize analyzer
        analyzer = BasicSectionAnalyzer()
        print("✅ Successfully initialized BasicSectionAnalyzer")
        
        # Run structural analysis
        sections = analyzer.cluster_repository(
            test_files,
            method=AnalysisMethod.STRUCTURAL,
            max_section_size=5,
            min_section_size=1
        )
        
        if sections:
            print(f"✅ Successfully created {len(sections)} sections")
            
            # Print section details
            for name, files in sections:
                print(f"  - Section '{name}' contains {len(files)} files")
            
            return True
        else:
            print("❌ Failed to create sections")
            return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_claude_api():
    """
    Test Claude API connection and basic functionality.
    This ensures the Claude integration works properly.
    """
    print("\n==== Testing Claude API Connection ====")
    
    # Check for Claude API key
    api_key = os.getenv('CLAUDE_API_KEY')
    if not api_key:
        print("❌ ERROR: No CLAUDE_API_KEY found in .env file")
        return False
    
    try:
        # Initialize batch analyzer
        batch_analyzer = BatchClaudeAnalyzer()
        print("✅ Successfully initialized BatchClaudeAnalyzer")
        
        # Test with a simple request
        test_content = {"test.py": "def hello_world():\n    print('Hello, World!')"}
        test_section = [("Test_Section", test_content)]
        
        result = batch_analyzer.analyze_sections_batch(
            test_section,
            query="What does this function do?",
            model="claude-3-5-haiku-20241022"  # Use the smallest model for fastest/cheapest test
        )
        
        if result and "Test_Section" in result:
            print("✅ Successfully received response from Claude API")
            return True
        else:
            print("❌ Failed to get response from Claude API")
            return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def run_all_tests():
    """Run all tests and report results."""
    print("==== Running Essential Tests ====")
    
    # Create test output directory
    os.makedirs("test_output", exist_ok=True)
    
    # Run tests
    github_result = test_github_connection()
    section_result = test_basic_section_analyzer()
    
    # Only run Claude test if user confirms (to avoid costs)
    run_claude_test = input("\nRun Claude API test? This will make an API call and may incur charges (y/N): ").lower() == 'y'
    claude_result = test_claude_api() if run_claude_test else "Skipped"
    
    # Print summary
    print("\n==== Test Summary ====")
    print(f"GitHub API Connection: {'✅ PASSED' if github_result else '❌ FAILED'}")
    print(f"Basic Section Analyzer: {'✅ PASSED' if section_result else '❌ FAILED'}")
    print(f"Claude API Connection: {'✅ PASSED' if claude_result == True else '❌ FAILED' if claude_result == False else '⏭️ SKIPPED'}")
    
    # Overall result
    essential_passed = github_result and section_result
    if run_claude_test:
        essential_passed = essential_passed and claude_result
    
    if essential_passed:
        print("\n✅ All essential tests PASSED!")
        return 0
    else:
        print("\n❌ Some essential tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())