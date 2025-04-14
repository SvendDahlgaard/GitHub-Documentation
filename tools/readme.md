# Section Analysis Visualization Tools

This directory contains tools to help visualize and understand how different section analysis methods organize code files.

## LLM Clustering Test

The `llm_cluster_test.py` script in the `tests` directory demonstrates the LLM-based clustering functionality and compares it with other sectioning methods.

### Usage

```bash
# Run in mock mode (no API calls)
python tests/llm_cluster_test.py --mock

# Run on a specific repository
python tests/llm_cluster_test.py --owner username --repo repository-name

# Customize section sizing
python tests/llm_cluster_test.py --max-section-size 10 --min-section-size 3
```

### Output

The test generates visualizations in the `test_output/llm_clustering` directory:

* `llm_clustering_results.md` - Markdown summary of sections created by LLM
* `llm_clustering_results.json` - Raw JSON data of the sections
* `section_method_comparison.md` - Comparison with other section methods

## Section Visualizer

The `section_visualizer.py` tool creates interactive HTML visualizations to explore and compare different sectioning methods.

### Usage

```bash
# Create a visualization for a single section method
python tools/section_visualizer.py --input test_output/llm_clustering/llm_clustering_results.json --output visualization.html --title "LLM Clustering Results"

# Compare multiple section methods
python tools/section_visualizer.py --compare llm=test_output/llm_clustering/llm_clustering_results.json structural=test_output/structural/test_sections.json dependency=test_output/dependency/test_sections.json --output comparison.html
```

### Features

The HTML visualizations include:

* Interactive expanding/collapsing of sections
* Search functionality for finding files or sections
* Sorting by section size or name
* Color-coded section sizes
* Comparison view showing how files are grouped in different methods

## Example Workflow

1. Run the LLM clustering test in mock mode:
   ```bash
   python tests/llm_cluster_test.py --mock
   ```

2. Examine the generated markdown files to see how the sections are organized.

3. Create an interactive visualization:
   ```bash
   python tools/section_visualizer.py --input test_output/llm_clustering_mock/llm_clustering_results.json --output visualization.html
   ```

4. Open the HTML file in a browser to explore the sections interactively.

5. When ready, run the test on a real repository:
   ```bash
   python tests/llm_cluster_test.py --owner SvendDahlgaard --repo GitHub-Documentation
   ```

6. Compare the results of different methods:
   ```bash
   python tools/section_visualizer.py --compare llm=test_output/llm_clustering/llm_clustering_results.json dependency=test_output/dependency/test_sections.json --output method_comparison.html
   ```