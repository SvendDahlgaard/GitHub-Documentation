import os
import json
import tempfile
import subprocess
import logging
import requests
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)

class ClaudeAnalyzer:
    """
    Class to analyze code using Claude AI, either via API or CLI.
    """
    
    def __init__(self, api_key=None, method="api", claude_executable=None):
        """
        Initialize the Claude analyzer.
        
        Args:
            api_key: Claude API key (required if method="api")
            method: Analysis method - "api" or "cli"
            claude_executable: Path to Claude CLI executable (required if method="cli")
        """
        self.method = method
        
        if method == "api":
            self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
            if not self.api_key:
                raise ValueError("Claude API key is required for API method. Set it in .env file or pass directly.")
        elif method == "cli":
            self.claude_executable = claude_executable or "claude"
            # Check if executable exists
            try:
                result = subprocess.run([self.claude_executable, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    logger.warning(f"Claude executable check failed: {result.stderr}")
            except Exception as e:
                logger.warning(f"Could not verify Claude executable: {e}")
        else:
            raise ValueError("Method must be 'api' or 'cli'")
    
    def analyze_code(self, section_name: str, files: Dict[str, str], query: str = None, context: str = None) -> str:
        """
        Analyze code using Claude.
        
        Args:
            section_name: Name of the code section
            files: Dictionary mapping file paths to contents
            query: Specific query about the code
            context: Additional context for the analysis
            
        Returns:
            Claude's analysis of the code
        """
        # Format the files for Claude
        files_content = ""
        for path, content in files.items():
            files_content += f"\n\n### File: {path}\n```\n{content}\n```\n"
        
        # Default query if none provided
        if not query:
            query = f"Analyze this section of code ('{section_name}'). Explain its purpose, key components, and how it fits into the larger codebase."
        
        # Create prompt with or without context
        if context:
            prompt = f"""Previously, I've analyzed other sections of this codebase and discovered: 

{context}

Now I'm analyzing the '{section_name}' section which contains these files:

{files_content}

{query}

Provide a detailed but concise analysis focusing on:
1. The purpose and functionality of this section
2. Key classes, functions, and design patterns
3. How this relates to the sections analyzed previously
4. Any notable implementation details
"""
        else:
            prompt = f"""I'm analyzing the '{section_name}' section of a codebase which contains these files:

{files_content}

{query}

Provide a detailed but concise analysis focusing on:
1. The purpose and functionality of this section
2. Key classes, functions, and design patterns
3. How this fits into a larger codebase
4. Any notable implementation details
"""
        
        # Call Claude based on method
        if self.method == "api":
            return self._analyze_with_api(prompt)
        else:
            return self._analyze_with_cli(prompt)
    
    def _analyze_with_api(self, prompt: str) -> str:
        """
        Analyze code using Claude API.
        
        Args:
            prompt: The prompt to send to Claude
            
        Returns:
            Claude's response
        """
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            data = {
                "model": "claude-3-opus-20240229",  # Use appropriate model
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code != 200:
                logger.error(f"Claude API error: {response.status_code} - {response.text}")
                return f"Error: Failed to get analysis from Claude API (Status code: {response.status_code})"
            
            result = response.json()
            return result["content"][0]["text"]
            
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return f"Error: {str(e)}"
    
    def _analyze_with_cli(self, prompt: str) -> str:
        """
        Analyze code using Claude CLI.
        
        Args:
            prompt: The prompt to send to Claude
            
        Returns:
            Claude's response
        """
        try:
            # Create a temporary file for the conversation
            with tempfile.NamedTemporaryFile(suffix='.txt', mode='w+') as temp_file:
                temp_file.write(prompt)
                temp_file.flush()
                
                # Call Claude with this conversation file
                logger.debug(f"Calling Claude CLI with file: {temp_file.name}")
                result = subprocess.run(
                    [self.claude_executable, "send", temp_file.name],
                    capture_output=True,
                    text=True,
                    timeout=180  # 3-minute timeout for analysis
                )
                
                if result.returncode != 0:
                    logger.error(f"Claude CLI error: {result.stderr}")
                    return f"Error: Failed to get analysis from Claude CLI"
                
                return result.stdout
                
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out")
            return "Error: Claude analysis timed out"
        except Exception as e:
            logger.error(f"Error calling Claude CLI: {e}")
            return f"Error: {str(e)}"