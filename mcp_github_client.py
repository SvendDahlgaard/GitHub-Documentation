import os
import base64
import re
import json
import subprocess
import logging
import time
from typing import List, Dict, Any, Optional, Set
import threading
from queue import Queue, Empty
from github_client_base import GitHubClientBase

logger = logging.getLogger(__name__)

# Define full paths to Node.js executables for Windows
NODE_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "node.exe")
NPM_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "npm.cmd")
NPX_PATH = os.path.join("C:", os.sep, "Program Files", "nodejs", "npx.cmd")

class MCPGitHubClient(GitHubClientBase):
    """Client that uses GitHub MCP server to interact with repositories directly."""
    
    def __init__(self, use_cache=True, timeout=30):
        """
        Initialize client with direct GitHub MCP server integration.
        
        Args:
            use_cache: Whether to use caching to reduce API calls
            timeout: Default timeout in seconds for MCP calls
        """
        super().__init__(use_cache=use_cache)
        self.timeout = timeout
        
        # Set the GitHub personal access token from environment if available
        self.github_token = os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            logger.warning("No GITHUB_TOKEN environment variable found. GitHub MCP may not authenticate properly.")
        
        # We'll skip checking the MCP GitHub server with --version as that can hang
        # and just assume it's either installed or we'll install it on demand
        logger.info("Skipping MCP GitHub server version check to avoid potential hanging")
        
        # Start the server process
        self._start_mcp_server()

        # Counter for request IDs
        self.request_id = 0
    
    def _start_mcp_server(self):
        """Start the MCP GitHub server as a subprocess."""
        try:
            # Use the full path to npx for Windows
            npx_command = NPX_PATH if os.path.exists(NPX_PATH) else "npx"
            
            # Create command to start the server
            cmd = [npx_command, "--yes", "@modelcontextprotocol/server-github"]
            
            # Add logging
            logger.info(f"Starting MCP GitHub server with command: {' '.join(cmd)}")
            
            # Create environment with GITHUB token
            env = os.environ.copy()
            if self.github_token:
                env["GITHUB_PERSONAL_ACCESS_TOKEN"] = self.github_token
            
            # Start the server process with a timeout
            # Setting up a non-blocking way to start the process
            logger.info("Starting server process with timeout protection...")
            
            def start_process():
                try:
                    return subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,  # Line buffered
                        env=env
                    )
                except Exception as e:
                    logger.error(f"Error in start_process: {e}")
                    return None
            
            # Use a thread with a timeout
            process_queue = Queue()
            process_thread = threading.Thread(
                target=lambda: process_queue.put(start_process())
            )
            process_thread.daemon = True
            process_thread.start()
            
            # Wait for the process to start or timeout
            try:
                self.server_process = process_queue.get(timeout=10)
                if not self.server_process:
                    raise Exception("Failed to start server process")
            except Empty:
                logger.error("Timeout starting MCP GitHub server")
                # Abandon the thread (it will be cleaned up when the program exits)
                raise Exception("Timeout starting MCP GitHub server")
            
            # Set up queues for responses and errors
            self.response_queue = Queue()
            self.error_queue = Queue()
            
            # Start reader threads
            self.stdout_thread = threading.Thread(
                target=self._read_stream, 
                args=(self.server_process.stdout, self.response_queue),
                daemon=True
            )
            self.stderr_thread = threading.Thread(
                target=self._read_stream, 
                args=(self.server_process.stderr, self.error_queue),
                daemon=True
            )
            
            self.stdout_thread.start()
            self.stderr_thread.start()
            
            # Wait briefly for server to initialize but don't block too long
            time.sleep(2)
            
            logger.info("MCP GitHub server process started")
            
        except Exception as e:
            logger.error(f"Failed to start MCP GitHub server: {e}")
            raise

    def _read_stream(self, stream, queue):
        """Read from a stream and put lines into a queue."""
        try:
            for line in iter(stream.readline, ''):
                if line.strip():
                    queue.put(line.strip())
        except (ValueError, IOError) as e:
            logger.error(f"Error reading from stream: {e}")
        finally:
            logger.debug("Stream reader thread exiting")
    
    def __del__(self):
        """Clean up server process when done."""
        if hasattr(self, 'server_process'):
            try:
                self.server_process.terminate()
                logger.info("Terminated MCP GitHub server process")
            except:
                pass
    
    def call_mcp_tool(self, tool_name: str, params: Dict[str, Any], 
                      custom_timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Call a GitHub MCP tool using the server process.
        
        Args:
            tool_name: Name of the MCP tool to call
            params: Parameters for the tool
            custom_timeout: Optional custom timeout in seconds
            
        Returns:
            Response from the tool
        """
        timeout = custom_timeout or self.timeout
        try:
            # Drain the error queue to get any previous errors
            while not self.error_queue.empty():
                error = self.error_queue.get_nowait()
                logger.debug(f"Drained previous error: {error}")
            
            # Drain the response queue to clear any previous responses
            while not self.response_queue.empty():
                resp = self.response_queue.get_nowait()
                logger.debug(f"Drained previous response: {resp}")

            # Increase and get the request ID
            self.request_id += 1
            request_id = str(self.request_id)
            
            # Prepare the request message
            request = {
                "type": "call_tool",
                "id": request_id,
                "params": {
                    "name": tool_name,
                    "arguments": params
                }
            }
            
            # Log the request for debugging
            logger.info(f"Calling MCP tool '{tool_name}' with request ID {request_id}")
            logger.debug(f"Request parameters: {json.dumps(params, indent=2)}")
            
            # Make sure server process is still running
            if not hasattr(self, 'server_process') or self.server_process.poll() is not None:
                logger.error("Server process is not running, cannot make request")
                raise Exception("MCP GitHub server is not running")
            
            # Convert request to JSON and send to the server
            request_json = json.dumps(request) + '\n'
            try:
                self.server_process.stdin.write(request_json)
                self.server_process.stdin.flush()
            except Exception as e:
                logger.error(f"Error sending request to server: {e}")
                raise Exception(f"Could not send request to MCP GitHub server: {e}")
            
            # Wait for response with timeout
            start_time = time.time()
            response = None
            
            while time.time() - start_time < timeout:
                # Check for errors
                try:
                    error = self.error_queue.get_nowait()
                    logger.warning(f"Server error: {error}")
                except Empty:
                    pass
                
                # Check for response
                try:
                    response_line = self.response_queue.get(timeout=0.1)
                    try:
                        response_data = json.loads(response_line)
                        if "id" in response_data and response_data["id"] == request_id:
                            response = response_data
                            break
                        else:
                            logger.debug(f"Received response for different request: {response_line}")
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON response: {response_line}")
                except Empty:
                    # No response yet, continue waiting
                    pass
                
                # Check if server is still running
                if self.server_process.poll() is not None:
                    exit_code = self.server_process.poll()
                    logger.error(f"Server process exited with code {exit_code} while waiting for response")
                    raise Exception(f"MCP GitHub server exited with code {exit_code}")
            
            if response is None:
                raise Exception(f"Timeout calling MCP tool {tool_name} after {timeout} seconds")
            
            # Process the response
            if "error" in response:
                logger.error(f"MCP tool call error: {response['error']}")
                raise Exception(f"Failed to call GitHub MCP tool {tool_name}: {response['error']}")
            
            # Extract the result from the response
            try:
                if "result" in response:
                    result = response["result"]
                    # For text content, the result is usually in the first content item
                    if "content" in result and len(result["content"]) > 0:
                        content_items = result["content"]
                        for item in content_items:
                            if item["type"] == "text":
                                try:
                                    return json.loads(item["text"])
                                except json.JSONDecodeError:
                                    # If it's not JSON, return the text directly
                                    return {"text": item["text"]}
                    
                    return result
                else:
                    logger.warning(f"Response has no 'result' field: {response}")
                    return response
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from response: {e}")
                logger.error(f"Response: {response}")
                raise Exception(f"Invalid JSON response from GitHub MCP tool {tool_name}")
                
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
            if isinstance(content, dict) and "content" in content and content.get("encoding") == "base64":
                decoded = base64.b64decode(content["content"]).decode('utf-8')
                logger.info(f"Successfully retrieved and decoded content for {path}")
                return decoded
            
            # If it's not encoded or we're dealing with an unexpected response format
            if isinstance(content, dict) and "content" in content:
                logger.warning(f"Content not base64 encoded, returning as-is")
                return content.get("content", "")
            
            logger.error(f"Unexpected response format from get_file_contents: {content}")
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
            
            if isinstance(repo_info, dict) and "total_count" in repo_info and repo_info.get("total_count", 0) > 0:
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
            }, custom_timeout=60)
            
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
            
            if isinstance(repo_info, dict) and "total_count" in repo_info and repo_info.get("total_count", 0) > 0:
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