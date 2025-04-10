import os
import json
import tempfile
import subprocess
import logging
import requests
from typing import Dict, List, Tuple, Any
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class ClaudeAnalyzer:
    """
    Class to analyze code using Claude AI, either via API or CLI.
    """
    
    def __init__(self, api_key=None, method="api", claude_executable=None, claude_model=None):
        """
        Initialize the Claude analyzer.
        
        Args:
            api_key: Claude API key (required if method="api")
            method: Analysis method - "api" or "cli"
            claude_executable: Path to Claude CLI executable (required if method="cli")
            claude_model: Claude model to use (defaults to latest available)
        """
        self.method = method
        self.claude_model = claude_model or "claude-3-7-sonnet-20250219"  # Updated to latest model
        
        if method == "api":
            self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
            if not self.api_key:
                raise ValueError("Claude API key is required for API method. Set it in .env file or pass directly.")
        elif method == "cli":
            self.claude_executable = claude_executable or "claude"
            # Check if executable exists and get version info
            try:
                # Check if --model flag is supported
                help_result = subprocess.run([self.claude_executable, "send", "--help"], 
                                capture_output=True, text=True, timeout=10)
                self.supports_model_flag = "--model" in help_result.stdout
                logger.info(f"Claude CLI supports --model flag: {self.supports_model_flag}")
            except Exception as e:
                logger.warning(f"Could not verify Claude executable: {e}")
                self.supports_model_flag = False
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
        
        # Process and optimize context if provided
        optimized_context = self._optimize_context(context) if context else None
        
        # Create prompt with or without context
        if optimized_context:
            prompt = f"""Previously, I've analyzed other sections of this codebase and discovered: 

{optimized_context}

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
    
    def _optimize_context(self, context: str, max_length: int = 8000) -> str:
        """
        Optimize context to fit within token limits while preserving important information.
        
        This function uses a combination of techniques:
        1. Extracts key points from previous analyses
        2. Prioritizes information based on relevance markers
        3. Trims context while preserving the most critical information
        
        Args:
            context: The context from previous analyses
            max_length: Maximum character length for the context
            
        Returns:
            Optimized context string
        """
        if not context or len(context) <= max_length:
            return context
            
        # Split by sections (assuming sections are separated by blank lines)
        sections = re.split(r'\n\s*\n', context)
        
        # Score and prioritize sections
        scored_sections = []
        for section in sections:
            # Calculate a relevance score based on heuristics
            score = 0
            
            # Prioritize based on section headers
            if "Section '" in section:
                score += 5
                
            # Higher score for sections mentioning functions/classes/key components
            if re.search(r'class\s+\w+|function\s+\w+|method\s+\w+', section, re.IGNORECASE):
                score += 3
                
            # Higher score for sections describing relationships
            if re.search(r'relates|connects|interfaces|communicates with', section, re.IGNORECASE):
                score += 4
                
            # Higher score for sections with key terms
            if re.search(r'purpose|primary|main|key|core|essential', section, re.IGNORECASE):
                score += 2
                
            # Add the scored section
            scored_sections.append((score, section))
        
        # Sort sections by score (highest first)
        scored_sections.sort(reverse=True)
        
        # Rebuild context prioritizing highest-scored sections
        optimized_context = []
        current_length = 0
        
        for score, section in scored_sections:
            section_length = len(section)
            
            # If adding this section would exceed max length, skip it
            if current_length + section_length + 2 > max_length:  # +2 for newlines
                continue
                
            optimized_context.append(section)
            current_length += section_length + 2  # +2 for newlines
        
        # Join sections back together with blank lines in between
        return "\n\n".join(optimized_context)
    
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
                "model": self.claude_model,  # Use the configured model
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
                
                # Configure command based on model flag support
                if hasattr(self, 'supports_model_flag') and self.supports_model_flag and "claude-3" in self.claude_model:
                    # Standard Claude CLI with model flag
                    logger.debug(f"Using Claude CLI with --model flag: {self.claude_model}")
                    cmd = [self.claude_executable, "send", "--model", self.claude_model, temp_file.name]
                else:
                    # Standard Claude CLI without model specification
                    logger.debug("Using standard Claude CLI command")
                    cmd = [self.claude_executable, "send", temp_file.name]
                
                logger.debug(f"Executing command: {' '.join(cmd)}")
                
                # Run the command with standard timeout
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=180
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr.strip()
                    logger.error(f"Claude CLI error: {error_msg}")
                    return f"Error: Failed to get analysis from Claude CLI\nCommand: {' '.join(cmd)}\nError: {error_msg}"
                
                # Check if we got a meaningful response
                if not result.stdout or len(result.stdout.strip()) < 10:
                    logger.error("Claude CLI returned empty or very short response")
                    return "Error: Claude CLI returned empty or very short response"
                
                return result.stdout
                
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out")
            return f"Error: Claude analysis timed out after 180 seconds"
        except Exception as e:
            logger.error(f"Error calling Claude CLI: {e}")
            return f"Error: {str(e)}"
            
    def _get_timestamp(self):
        """Get current timestamp for logging and file naming."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")