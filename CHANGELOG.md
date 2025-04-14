# Changelog

## 2025-04-14: Simplified Architecture

### Removed

- **MCP GitHub Client**: Removed MCP-based GitHub client and all related code
- **Claude CLI Integration**: Removed support for using the Claude CLI
- **Multiple Client Options**: Simplified to only use the direct GitHub API client

### Changed

- **Renamed Direct GitHub Client**: Renamed to `GithubClient.py` and incorporated the base class functionality
- **Default Section Method**: Changed default section method to `llm_cluster` for better section organization
- **Simplified Analysis**: Now always using batch analysis for efficiency
- **Updated Documentation**: Updated README with simplified usage instructions

### Added

- **Better Error Handling**: Improved error messages during repository analysis
- **Performance Improvements**: More efficient file processing with better batching

## Benefits of Changes

1. **Simplified Codebase**: Removed overlapping and redundant functionality
2. **Clear Execution Path**: More intuitive workflow with fewer configuration options
3. **Better Defaults**: Uses the most effective section analysis method by default
4. **Improved Efficiency**: Always uses batch analysis for better performance