# GitHub MCP Integration Guide

This guide explains how to use the GitHub Model Context Protocol (MCP) integration to improve code analysis in the GitHub-Documentation tool.

## Overview

The GitHub MCP integration enhances code analysis by leveraging the GitHub MCP server's capabilities, particularly code search functionality, to better understand relationships between files. This creates more meaningful section groupings for your documentation.

## Prerequisites

To use the GitHub MCP integration, you need:

1. **Node.js and npm** installed on your system (required for the GitHub MCP server)
2. A valid **GitHub token** in your `.env` file
3. The GitHub MCP server package installed:
   ```bash
   npm install -g @modelcontextprotocol/server-github
   ```

## Usage

To use the GitHub MCP integration, run the Repo-analyzer with the `--client-type mcp` flag:

```bash
python Repo-analyzer.py --owner <username> --repo <repository-name> --client-type mcp --section-method dependency
```

### Key Parameters

- `--client-type mcp`: Use the MCP GitHub client instead of the direct client
- `--section-method dependency`: Use dependency analysis (recommended with MCP)
- `--section-method hybrid`: Use hybrid analysis for even better results
- `--use-context`: Enable context preservation between sections

### Example Full Command

```bash
python Repo-analyzer.py --owner SvendDahlgaard --repo GitHub-Documentation --client-type mcp --section-method hybrid --use-context --query "Explain what this section does and how it relates to the rest of the codebase."
```

## How It Works

1. The MCP GitHub client launches the GitHub MCP server as a subprocess
2. The client communicates with the server to make GitHub API calls
3. The `AdvancedSectionAnalyzer` uses GitHub's code search to find references between files
4. These references are used to build a dependency graph
5. Files are grouped into logical sections based on this enhanced dependency information

## Advantages Over Direct GitHub API

The MCP-enhanced analysis offers several advantages:

1. **Deeper understanding of code relationships**: Identifies references that simple import parsing misses
2. **Better section grouping**: Creates more natural and logical code groupings
3. **Handling of complex codebases**: Works well with repositories where functionality is spread across multiple directories

## Troubleshooting

If you encounter issues:

1. Ensure Node.js and npm are installed
2. Verify your GitHub token is valid and has appropriate permissions
3. Check if you can run the GitHub MCP server manually:
   ```bash
   npx -y @modelcontextprotocol/server-github
   ```
4. Review the logs for specific error messages

For more detailed troubleshooting assistance, run the analyzer with the `--verbose` flag:

```bash
python Repo-analyzer.py --owner <username> --repo <repository-name> --client-type mcp --verbose
```