import os
import base64
import re
import json
import subprocess
import logging
import tempfile
import time
from typing import List, Dict, Any, Optional, Set
from github_client_base import GitHubClientBase

logger = logging.getLogger(__name__)

class MCPGitHubClient(GitHubClientBase):
    """Client that uses GitHub MCP server to interact with repositories."""
    
    def __init__(self, use_cache=True, claude_executable=None, timeout=240):
        """
        Initialize client with Claude CLI for MCP commands.
        
        Args:
            use_cache: Whether to use caching to reduce API calls
            claude_executable: Path to Claude executable for MCP commands
            timeout: Default timeout in seconds for MCP calls
        """
        super().__init__(use_cache=use_cache)
        self.claude_executable = claude_executable or "claude"
        self.timeout = timeout
        
        # Set the GitHub personal access token from environment if available
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
            logger.info("Using GitHub token from GITHUB_TOKEN environment variable")
        else:
            logger.warning("No GITHUB_TOKEN environment variable found. GitHub MCP may not authenticate properly.")
        
        # Verify Claude CLI is available
        self._check_claude_cli()
    
    def _check_claude_cli(self):
        """Verify Claude CLI is available and print its version."""
        try:
            result = subprocess.run(
                [self.claude_executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Claude CLI version: {result.stdout.strip()}")
            else:
                logger.warning(f"Claude CLI test returned non-zero exit code: {result.returncode}")
                logger.warning(f"Claude CLI stderr: {result.stderr}")
        except FileNotFoundError:
            logger.error(f"Claude CLI executable not found: {self.claude_executable}")
            logger.info("Please install Claude CLI using: npm install -g @anthropic-ai/claude-cli")
        except subprocess.TimeoutExpired:
            logger.warning("Claude CLI version check timed out, this might indicate slow response times")
        except Exception as e:
            logger.warning(f"Error checking Claude CLI: {e}")
    
    def call_mcp_tool(self, tool_name: str, params: Dict[str, Any], custom_timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Call a GitHub MCP tool using Claude CLI.
        
        Args:
            tool_name: Name of the MCP tool to call
            params: Parameters for the tool
            custom_timeout: Optional custom timeout in seconds
            
        Returns:
            Response from the tool
        """
        # Use custom timeout if provided, otherwise use the default
        timeout = custom_timeout if custom_timeout is not None else self.timeout
        logger.debug(f"Calling MCP tool '{tool_name}' with timeout {timeout}s")
        logger.debug(f"Parameters: {json.dumps(params, indent=2)}")
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.txt', mode='w+', delete=False) as temp_file:
                # Store temp file path for cleanup
                temp_file_path = temp_file.name
                
                # Create the prompt for Claude to use the GitHub MCP tool
                prompt = f"""
                I need to use the GitHub MCP tool "{tool_name}" with the following parameters:
                ```json
                {json.dumps(params, indent=2)}
                ```
                
                Please execute this MCP tool and return only the raw JSON response without any additional text, explanation, or formatting.
                """
                
                temp_file.write(prompt)
                temp_file.flush()
                
                # Log command for debugging
                cmd = [self.claude_executable, "send", "--print", temp_file_path]
                logger.debug(f"Executing command: {' '.join(cmd)}")
                
                # Record start time
                start_time = time.time()
                logger.info(f"Starting MCP tool call to '{tool_name}' at {time.strftime('%H:%M:%S')}")
                
                # Execute the Claude CLI command
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    
                    execution_time = time.time() - start_time
                    logger.info(f"MCP tool call completed in {execution_time:.2f} seconds")
                    
                    if result.returncode != 0:
                        logger.error(f"Claude MCP call error: {result.stderr}")
                        logger.error(f"Exit code: {result.returncode}")
                        logger.error(f"Stdout: {result.stdout[:500]}...")
                        raise Exception(f"Failed to call GitHub MCP tool {tool_name}")
                    
                    # Parse the JSON response from Claude's output
                    output = result.stdout
                    logger.debug(f"Raw output: {output[:1000]}...")
                    
                    # Extract JSON from the output (might be in code blocks)
                    json_match = re.search(r'```(?:json)?\n([\s\S]*?)\n```', output)
                    if json_match:
                        json_str = json_match.group(1).strip()
                        logger.debug("Found JSON in code block")
                    else:
                        # Try to find raw JSON if not in code blocks
                        json_str = output.strip()
                        logger.debug("No JSON code block found, using raw output")
                    
                    # Parse the JSON string
                    try:
                        result_data = json.loads(json_str)
                        return result_data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from response: {e}")
                        logger.error(f"JSON string: {json_str[:500]}...")
                        
                        # Check if the output contains an authentication error message
                        if "Invalid API key" in output or "Please run /login" in output:
                            logger.error("Authentication error with Claude CLI. Please run 'claude login' to authenticate.")
                            raise Exception(f"Claude CLI authentication failed. Please run 'claude login' to authenticate.")
                        
                        raise Exception(f"Invalid JSON response from GitHub MCP tool {tool_name}")
                    
                except subprocess.TimeoutExpired:
                    elapsed_time = time.time() - start_time
                    logger.error(f"MCP tool call timed out after {elapsed_time:.2f} seconds (timeout was {timeout}s)")
                    raise Exception(f"Timeout calling GitHub MCP tool {tool_name}")
                finally:
                    # Clean up the temp file
                    try:
                        if os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file: {e}")
                
        except Exception as e:
            logger.error(f"Error calling GitHub MCP tool {tool_name}: {e}")
            raise
    
    def _list_repository_files(self, owner: str, repo: str, path: str = "", branch: str = None) -> List[Dict[str, Any]]:
        """
        List files in a repository path using MCP.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Path in the repository
            branch: Branch to use
            
        Returns:
            List of file information dictionaries
        """
        logger.info(f"Listing repository files for {owner}/{repo}, path: '{path}'")
        
        try:
            contents = self.call_mcp_tool("get_file_contents", {
                "owner": owner,
                "repo": repo,
                "path": path,
                "branch": branch
            })
            
            # Handle both single file and directory cases
            if not isinstance(contents, list):
                contents = [contents]
                
            result = []
            for content in contents:
                item = {
                    "name": content.get("name", ""),
                    "path": content.get("path", ""),
                    "type": "file" if content.get("type") == "file" else "dir",
                    "size": content.get("size", 0)
                }
                result.append(item)
                
            logger.info(f"Found {len(result)} items in {owner}/{repo} at path '{path}'")
            return result
            
        except Exception as e:
            logger.error(f"Error listing repository files: {e}")
            # Return empty list rather than failing
            return []
    
    def _get_file_content(self, owner: str, repo: str, path: str, branch: str = None) -> str:
        """
        Get the content of a file using MCP.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to the file
            branch: Branch to use
            
        Returns:
            Content of the file as string
        """
        logger.info(f"Getting file content for {owner}/{repo}, path: '{path}'")
        
        try:
            content = self.call_mcp_tool("get_file_contents", {
                "owner": owner,
                "repo": repo,
                "path": path,
                "branch": branch
            })
            
            # The content is returned as a base64-encoded string
            if "content" in content and content.get("encoding") == "base64":
                decoded = base64.b64decode(content["content"]).decode('utf-8')
                logger.info(f"Successfully retrieved and decoded content for {path}")
                return decoded
            
            # If it's not encoded or we're dealing with an unexpected response format
            if "content" in content:
                logger.warning(f"Content not base64 encoded, returning as-is")
                return content.get("content", "")
            
            logger.error(f"Unexpected response format from get_file_contents")
            return ""
            
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            raise
    
    def _get_default_branch(self, owner: str, repo: str) -> str:
        """
        Get the default branch for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Name of the default branch
        """
        logger.info(f"Getting default branch for {owner}/{repo}")
        
        try:
            # Search for the repository to get its details
            repo_info = self.call_mcp_tool("search_repositories", {
                "query": f"repo:{owner}/{repo}"
            })
            
            if repo_info.get("total_count", 0) > 0:
                items = repo_info.get("items", [])
                if items and len(items) > 0:
                    branch = items[0].get("default_branch")
                    if branch:
                        logger.info(f"Default branch for {owner}/{repo}: {branch}")
                        return branch
            
            logger.warning(f"Could not determine default branch from search results, using fallback")
            
        except Exception as e:
            logger.error(f"Error getting default branch: {e}")
        
        # Fallback to 'main' if we couldn't determine the default branch
        logger.info("Using fallback branch 'main'")
        return "main"
    
    def search_code(self, owner: str, repo: str, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search for code in a repository using the GitHub code search API.
        
        Args:
            owner: Repository owner
            repo: Repository name
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of search result items
        """
        logger.info(f"Searching code in {owner}/{repo} with query: '{query}'")
        
        try:
            # Add repo: prefix if not already present
            if f"repo:{owner}/{repo}" not in query:
                query = f"repo:{owner}/{repo} {query}"
                logger.info(f"Modified query to: '{query}'")
                
            # Call the search_code tool with a longer timeout
            response = self.call_mcp_tool("search_code", {
                "q": query,
                "per_page": min(100, max_results)
            }, custom_timeout=120)
            
            items = response.get("items", [])
            total_count = response.get("total_count", 0)
            
            logger.info(f"Found {total_count} matches, returning {len(items)} items")
            return items[:max_results]
            
        except Exception as e:
            logger.error(f"Error searching code in {owner}/{repo}: {e}")
            return []
    
    def search_references(self, owner: str, repo: str, filepath: str) -> Set[str]:
        """
        Search for all files that reference a specific file.
        
        Args:
            owner: Repository owner
            repo: Repository name
            filepath: Path to the file to find references for
            
        Returns:
            Set of filepaths that reference the specified file
        """
        logger.info(f"Searching for references to {filepath} in {owner}/{repo}")
        
        try:
            # Extract filename and extension
            filename = os.path.basename(filepath)
            name, ext = os.path.splitext(filename)
            
            # Create search queries based on file type
            queries = []
            
            # Search by exact filename
            queries.append(f"\"{filename}\"")
            
            # For Python files, search for imports
            if ext == '.py':
                module_name = name
                if name == '__init__':
                    # For __init__.py, search for the directory name
                    dir_name = os.path.basename(os.path.dirname(filepath))
                    if dir_name:
                        module_name = dir_name
                
                # Search for both import statements
                queries.append(f"\"import {module_name}\"")
                queries.append(f"\"from {module_name}\"")
            
            # Run searches and combine results
            references = set()
            for query in queries:
                logger.info(f"Searching with query: '{query}'")
                try:
                    search_results = self.search_code(owner, repo, query)
                    
                    for item in search_results:
                        # Skip the file itself
                        if item.get("path") == filepath:
                            continue
                        
                        references.add(item.get("path"))
                    
                    logger.info(f"Found {len(search_results)} potential references with query '{query}'")
                    
                except Exception as e:
                    logger.warning(f"Error in search query '{query}': {e}")
                    # Continue with other queries
            
            logger.info(f"Total unique references found: {len(references)}")
            return references
            
        except Exception as e:
            logger.error(f"Error searching references for {filepath}: {e}")
            return set()
    
    def get_repository_stats(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get repository statistics and metadata.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Dictionary with repository statistics
        """
        logger.info(f"Getting repository stats for {owner}/{repo}")
        
        try:
            repo_info = self.call_mcp_tool("search_repositories", {
                "query": f"repo:{owner}/{repo}"
            })
            
            if repo_info.get("total_count", 0) > 0:
                items = repo_info.get("items", [])
                if items and len(items) > 0:
                    repo_data = items[0]
                    
                    stats = {
                        "name": repo_data.get("name"),
                        "full_name": repo_data.get("full_name"),
                        "description": repo_data.get("description"),
                        "default_branch": repo_data.get("default_branch"),
                        "language": repo_data.get("language"),
                        "stars": repo_data.get("stargazers_count"),
                        "forks": repo_data.get("forks_count"),
                        "open_issues": repo_data.get("open_issues_count"),
                        "created_at": repo_data.get("created_at"),
                        "updated_at": repo_data.get("updated_at"),
                        "is_private": repo_data.get("private", False),
                        "is_archived": repo_data.get("archived", False),
                        "license": repo_data.get("license", {}).get("name") if repo_data.get("license") else None
                    }
                    
                    logger.info(f"Successfully retrieved stats for {owner}/{repo}")
                    return stats
            
            logger.warning(f"Could not get repository stats for {owner}/{repo}")
            return {}
            
        except Exception as e:
            logger.error(f"Error getting repository stats: {e}")
            return {}