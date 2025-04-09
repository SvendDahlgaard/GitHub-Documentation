# GitHub-Documentation

A tool for automatically analyzing GitHub repositories and generating comprehensive documentation using Claude AI.

## Overview

GitHub-Documentation scans repositories, divides them into logical sections, and uses Claude to generate detailed documentation for each section. The tool maintains context between sections to ensure coherent documentation across the entire codebase.

## Features

- **Multiple Section Analysis Methods**: Choose from structural, dependency-based, or hybrid sectioning algorithms
- **Flexible Claude Integration**: Works with both Claude API and CLI
- **Smart Context Management**: Maintains and optimizes context between sections
- **Customizable Documentation**: Configure specific queries for each section
- **Repository Caching**: Cache repository files to avoid repeated API calls

## Section Analysis Methods

The tool supports three different methods for dividing repositories into logical sections:

### 1. Structural Analysis (Default)

Groups files based on directory structure and then subdivides large sections based on file types or naming patterns. This works best for repositories with a clear directory organization.

### 2. Dependency Analysis

Analyzes import and dependency relationships between files to create sections of related code. This is useful for repositories where functionality is spread across multiple directories.

### 3. Hybrid Analysis

Combines both structural and dependency-based approaches. First groups files by directory, then refines large sections using dependency analysis. This often produces the most logical grouping for complex codebases.

## Claude Integration

The tool integrates with Claude AI to analyze and document each section. It supports:

- **Latest Claude Models**: Works with Claude 3.7 Sonnet and other Claude 3 models
- **Context Preservation**: Summarizes important information from previous sections to maintain context
- **Optimized Prompting**: Structures prompts to get the most useful analysis from Claude

## Usage

```bash
python Repo-analyzer.py --owner <github-username> --repo <repository-name> [options]
```

### Example

```bash
python Repo-analyzer.py --owner SvendDahlgaard --repo GitHub-Documentation --section-method hybrid --query "Explain what this section does and how it relates to the rest of the codebase." --use-context
```

### Options

- `--section-method`: Choose from `structural`, `dependency`, or `hybrid` (default: `structural`)
- `--use-context`: Enable context preservation between sections
- `--max-section-size`: Maximum number of files in a section before subdivision (default: 15)
- `--min-section-size`: Minimum number of files in a section (default: 1)
- `--claude-executable`: Path to Claude CLI executable (for CLI method)
- `--analysis-method`: Choose `api` or `cli` for Claude analysis (default: `cli`)

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your GitHub token: `GITHUB_TOKEN=your_token_here`
4. If using the Claude API, add your API key: `CLAUDE_API_KEY=your_api_key_here`
5. Run tests to verify setup: `cd tests && python run_tests.py`

## Testing

You can test different components of the system:

```bash
cd tests

# Test GitHub token
python github_token_test.py

# Test section analyzer
python section_analyzer_test.py

# Test Claude integration
python claude_test.py

# Run all tests
python run_tests.py
```
