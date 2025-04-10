#!/usr/bin/env python3
"""
Test BatchClaudeAnalyzer functionality for cost-efficient batch processing.
"""
import os
import sys
import json
from dotenv import load_dotenv
sys.path.append('..')  # Add parent directory to path
from batch_claude_analyzer import BatchClaudeAnalyzer

def test_batch_analyzer():
    """Test BatchClaudeAnalyzer's ability to process multiple code sections efficiently."""
    # Load environment variables
    load_dotenv()
    
    # Check for API key
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        print("ERROR: No CLAUDE_API_KEY found in .env file")
        print("Batch analysis requires an API key. Set it in .env file or pass directly.")
        return False
    
    print("Testing BatchClaudeAnalyzer capabilities...")
    
    # Ensure test_output directory exists
    os.makedirs("test_output", exist_ok=True)
    
    # Sample code sections to analyze
    section1 = {
        "sample1.py": """
def hello_world():
    \"\"\"Print a hello world message.\"\"\"
    print("Hello, World!")
    
class Calculator:
    \"\"\"A simple calculator class.\"\"\"
    
    def add(self, a, b):
        \"\"\"Add two numbers.\"\"\"
        return a + b
        
    def subtract(self, a, b):
        \"\"\"Subtract b from a.\"\"\"
        return a - b
"""
    }
    
    section2 = {
        "advanced.py": """
class AdvancedCalculator(Calculator):
    \"\"\"An advanced calculator that extends the basic Calculator.\"\"\"
    
    def multiply(self, a, b):
        \"\"\"Multiply two numbers.\"\"\"
        return a * b
        
    def divide(self, a, b):
        \"\"\"Divide a by b.\"\"\"
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
"""
    }
    
    # Prepare sections for batch analysis
    sections = [
        ("Calculator", section1),
        ("AdvancedCalculator", section2)
    ]
    
    try:
        # Initialize BatchClaudeAnalyzer
        print("\nInitializing BatchClaudeAnalyzer with Claude 3.5 Haiku...")
        batch_analyzer = BatchClaudeAnalyzer(
            claude_model="claude-3-5-haiku-20241022",  # Most cost-effective model
            use_prompt_caching=True
        )
        print("✓ Successfully initialized BatchClaudeAnalyzer")
        
        # Test batch analysis
        print("\nTesting batch analysis of multiple code sections...")
        print("This may take a few minutes as the batch is processed...")
        
        # Create a simple query
        query = "Analyze this code section briefly. What does it do and how is it structured?"
        
        # Process the batch
        try:
            results = batch_analyzer.analyze_sections_batch(sections, query)
            
            if not results:
                print("× Batch analysis failed: No results returned")
                return False
                
            print(f"✓ Successfully analyzed {len(results)} sections in batch")
            
            # Save results to test_output directory
            batch_output_path = os.path.join("test_output", "batch_analysis_results.json")
            with open(batch_output_path, "w") as f:
                # Store metadata and results
                output_data = {
                    "timestamp": batch_analyzer._get_timestamp(),
                    "query": query,
                    "sections": [section_name for section_name, _ in sections],
                    "results": results
                }
                json.dump(output_data, f, indent=2)
            
            print(f"✓ Saved batch analysis results to {batch_output_path}")
            
            # Also save individual markdown files for each section
            for section_name, analysis in results.items():
                md_path = os.path.join("test_output", f"batch_analysis_{section_name}.md")
                with open(md_path, "w") as f:
                    f.write(f"# Analysis of {section_name}\n\n")
                    f.write(analysis)
                print(f"✓ Saved {section_name} analysis to {md_path}")
            
            # Print sample of results
            for section_name, analysis in results.items():
                print(f"\nAnalysis for section '{section_name}':")
                print("-" * 40)
                print(analysis[:200] + "..." if len(analysis) > 200 else analysis)
                print("-" * 40)
                
            # Test with context between sections
            print("\nTesting batch analysis with context between sections...")
            
            # Create a context map
            context_map = {
                "AdvancedCalculator": "Section 'Calculator': This section defines basic calculator functionality with add and subtract operations."
            }
            
            results_with_context = batch_analyzer.analyze_sections_batch(
                [sections[1]],  # Just the AdvancedCalculator section
                query,
                context_map
            )
            
            if not results_with_context:
                print("× Batch analysis with context failed: No results returned")
            else:
                section_name = "AdvancedCalculator"
                print(f"\nAnalysis for section '{section_name}' with context:")
                print("-" * 40)
                analysis = results_with_context.get(section_name, "")
                print(analysis[:200] + "..." if len(analysis) > 200 else analysis)
                print("-" * 40)
                print("✓ Successfully analyzed section with context")
                
                # Save contextualized results
                context_md_path = os.path.join("test_output", f"batch_analysis_{section_name}_with_context.md")
                with open(context_md_path, "w") as f:
                    f.write(f"# Analysis of {section_name} with Context\n\n")
                    f.write(f"## Context Used\n\n```\n{context_map[section_name]}\n```\n\n")
                    f.write("## Analysis\n\n")
                    f.write(analysis)
                print(f"✓ Saved contextualized analysis to {context_md_path}")
            
            return True
            
        except Exception as e:
            print(f"× Batch analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to initialize BatchClaudeAnalyzer: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mock_batch():
    """
    Test BatchClaudeAnalyzer functionality without making actual API calls.
    This is useful for testing the integration without incurring costs.
    """
    print("Testing BatchClaudeAnalyzer with mock responses...")
    
    # Ensure test_output directory exists
    os.makedirs("test_output", exist_ok=True)
    
    # Sample code sections
    sections = [
        ("Section1", {"file1.py": "print('Hello World')"}),
        ("Section2", {"file2.py": "def add(a, b): return a + b"})
    ]
    
    # Mock the analyze_sections_batch method
    class MockBatchAnalyzer:
        def analyze_sections_batch(self, sections, query=None, context_map=None):
            print(f"Would analyze {len(sections)} sections in batch")
            print("Sections to analyze:")
            for name, files in sections:
                print(f" - {name}: {len(files)} files")
            
            # Return mock results
            return {name: f"Mock analysis of {name} section" for name, _ in sections}
            
        def _get_timestamp(self):
            """Helper method to get current timestamp for consistency with real class"""
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Use the mock analyzer
    mock_analyzer = MockBatchAnalyzer()
    results = mock_analyzer.analyze_sections_batch(sections)
    
    print("\nMock results:")
    for section, analysis in results.items():
        print(f" - {section}: {analysis}")
    
    # Save mock results to test_output directory
    mock_output_path = os.path.join("test_output", "mock_batch_analysis_results.json")
    with open(mock_output_path, "w") as f:
        # Store metadata and results
        output_data = {
            "timestamp": mock_analyzer._get_timestamp(),
            "query": "Mock query",
            "sections": [section_name for section_name, _ in sections],
            "results": results,
            "mode": "mock"
        }
        json.dump(output_data, f, indent=2)
    
    print(f"✓ Saved mock batch analysis results to {mock_output_path}")
    
    return True

if __name__ == "__main__":
    print("=== BatchClaudeAnalyzer Test ===")
    
    # Check if we should run with mock responses
    mock_mode = "--mock" in sys.argv
    
    if mock_mode:
        success = test_mock_batch()
    else:
        print("IMPORTANT: This test will make actual API calls to Anthropic and incur costs.")
        print("To run without making API calls, use the --mock flag.")
        confirmation = input("Do you want to continue with the real API test? (y/N): ")
        
        if confirmation.lower() == 'y':
            success = test_batch_analyzer()
        else:
            print("Test cancelled. Running with mock responses instead.")
            success = test_mock_batch()
    
    if success:
        print("\n✓ BatchClaudeAnalyzer test completed successfully!")
        sys.exit(0)
    else:
        print("\n× Some BatchClaudeAnalyzer tests failed!")
        sys.exit(1)