import os
import json
import tempfile
import time
import logging
import requests
from typing import Dict, List, Tuple, Any, Optional
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class BatchClaudeAnalyzer:
    """
    Class to analyze code using Claude AI via the Anthropic API with batch processing and prompt caching.
    This implementation offers significant cost savings through:
    1. Batch processing (50% discount)
    2. Prompt caching (90% discount on cache hits)
    3. Using Claude 3.5 Haiku for cost efficiency
    """
    
    def __init__(self, api_key=None, claude_model=None, use_prompt_caching=True):
        """
        Initialize the batch Claude analyzer.
        
        Args:
            api_key: Claude API key (required)
            claude_model: Claude model to use (defaults to Claude 3.5 Haiku for cost efficiency)
            use_prompt_caching: Whether to use prompt caching for additional cost savings
        """
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("Claude API key is required. Set it in .env file or pass directly.")
            
        # Default to Claude 3.5 Haiku for best cost efficiency
        self.claude_model = claude_model or "claude-3-5-haiku-20241022"
        self.use_prompt_caching = use_prompt_caching
        
        # Validate API key with a simple test request
        try:
            self._test_api_connection()
            logger.info(f"Successfully connected to Anthropic API using model: {self.claude_model}")
        except Exception as e:
            logger.error(f"Failed to connect to Anthropic API: {e}")
            raise
    
    def _test_api_connection(self):
        """Test the API connection with a simple request."""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        data = {
            "model": self.claude_model,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hello, this is a test."}]
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"API connection test failed: {response.status_code} - {response.text}")
    
    def analyze_sections_batch(self, sections: List[Tuple[str, Dict[str, str]]], 
                              query: Optional[str] = None, 
                              context_map: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Analyze multiple code sections in a batch for optimal cost efficiency.
        
        Args:
            sections: List of (section_name, files) tuples
            query: Specific query about the code sections
            context_map: Optional map of section_name to context string
            
        Returns:
            Dictionary mapping section names to analysis results
        """
        if not sections:
            return {}
            
        # Default query if none provided
        if not query:
            query = "Analyze this section of code. Explain its purpose, key components, and how it fits into the larger codebase."
        
        # Prepare batch requests
        batch_requests = []
        
        for section_name, files in sections:
            # Format the files for Claude
            files_content = ""
            for path, content in files.items():
                files_content += f"\n\n### File: {path}\n```\n{content}\n```\n"
            
            # Get context for this section if available
            section_context = context_map.get(section_name) if context_map else None
            
            # Create prompt with or without context
            if section_context:
                # Use prompt caching for the context if enabled
                if self.use_prompt_caching:
                    system_blocks = [
                        {
                            "type": "text",
                            "text": f"Previously, I've analyzed other sections of this codebase and discovered: \n\n{section_context}",
                            "cache_control": {"type": "ephemeral"}
                        },
                        {
                            "type": "text",
                            "text": f"Now I'm analyzing the '{section_name}' section which contains these files:"
                        }
                    ]
                else:
                    system_blocks = [
                        {
                            "type": "text",
                            "text": f"Previously, I've analyzed other sections of this codebase and discovered: \n\n{section_context}\n\nNow I'm analyzing the '{section_name}' section which contains these files:"
                        }
                    ]
                
                messages = [
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text",
                                "text": f"{files_content}\n\n{query}\n\nProvide a detailed but concise analysis focusing on:\n1. The purpose and functionality of this section\n2. Key classes, functions, and design patterns\n3. How this relates to the sections analyzed previously\n4. Any notable implementation details"
                            }
                        ]
                    }
                ]
            else:
                # No context to cache, use a simpler prompt
                system_blocks = [
                    {
                        "type": "text",
                        "text": f"I'm analyzing the '{section_name}' section of a codebase."
                    }
                ]
                
                messages = [
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text",
                                "text": f"{files_content}\n\n{query}\n\nProvide a detailed but concise analysis focusing on:\n1. The purpose and functionality of this section\n2. Key classes, functions, and design patterns\n3. How this fits into a larger codebase\n4. Any notable implementation details"
                            }
                        ]
                    }
                ]
            
            # Create the batch request entry
            batch_requests.append({
                "custom_id": section_name,
                "params": {
                    "model": self.claude_model,
                    "max_tokens": 3000,
                    "system": system_blocks,
                    "messages": messages
                }
            })
        
        # Send the batch request
        return self._process_batch(batch_requests)
    
    def _process_batch(self, batch_requests: List[Dict]) -> Dict[str, str]:
        """
        Process a batch of requests using the Anthropic Batch API.
        
        Args:
            batch_requests: List of batch request objects
            
        Returns:
            Dictionary mapping section names to analysis results
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Create batch
        logger.info(f"Creating batch with {len(batch_requests)} requests")
        
        create_response = requests.post(
            "https://api.anthropic.com/v1/messages/batches",
            headers=headers,
            json={"requests": batch_requests},
            timeout=30
        )
        
        if create_response.status_code != 200:
            logger.error(f"Failed to create batch: {create_response.status_code} - {create_response.text}")
            raise Exception(f"Failed to create batch: {create_response.text}")
        
        batch_data = create_response.json()
        batch_id = batch_data.get("id")
        logger.info(f"Successfully created batch with ID: {batch_id}")
        
        # Poll for batch completion
        max_polls = 120  # 2 hours max (with 1 minute intervals)
        for i in range(max_polls):
            logger.info(f"Polling batch status ({i+1}/{max_polls})...")
            
            status_response = requests.get(
                f"https://api.anthropic.com/v1/messages/batches/{batch_id}",
                headers=headers,
                timeout=30
            )
            
            if status_response.status_code != 200:
                logger.error(f"Failed to get batch status: {status_response.status_code} - {status_response.text}")
                continue
            
            status_data = status_response.json()
            processing_status = status_data.get("processing_status")
            request_counts = status_data.get("request_counts", {})
            
            logger.info(f"Batch status: {processing_status}, Counts: {request_counts}")
            
            # Check if batch has ended
            if processing_status == "ended":
                results_url = status_data.get("results_url")
                if results_url:
                    return self._retrieve_batch_results(results_url, headers)
                else:
                    logger.error("Batch ended but no results URL provided")
                    return {}
            
            # Wait before polling again (1 minute)
            time.sleep(60)
        
        logger.error(f"Batch processing timed out after {max_polls} polls")
        return {}
    
    def _retrieve_batch_results(self, results_url: str, headers: Dict) -> Dict[str, str]:
        """
        Retrieve and process batch results.
        
        Args:
            results_url: URL to retrieve batch results
            headers: Request headers
            
        Returns:
            Dictionary mapping section names to analysis results
        """
        logger.info(f"Retrieving batch results from: {results_url}")
        
        response = requests.get(results_url, headers=headers, timeout=60)
        
        if response.status_code != 200:
            logger.error(f"Failed to retrieve batch results: {response.status_code} - {response.text}")
            return {}
        
        results = {}
        
        # Process the JSONL response
        for line in response.text.strip().split('\n'):
            try:
                result_data = json.loads(line)
                custom_id = result_data.get("custom_id")
                result = result_data.get("result", {})
                
                if result.get("type") == "succeeded":
                    message = result.get("message", {})
                    content = message.get("content", [])
                    
                    # Extract text from content blocks
                    text_content = ""
                    for block in content:
                        if block.get("type") == "text":
                            text_content += block.get("text", "")
                    
                    results[custom_id] = text_content
                else:
                    error_type = result.get("error", {}).get("type", "unknown")
                    error_message = result.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Error processing section '{custom_id}': {error_type} - {error_message}")
                    results[custom_id] = f"Error: {error_message}"
            except json.JSONDecodeError:
                logger.error(f"Failed to parse result line: {line}")
        
        logger.info(f"Successfully retrieved results for {len(results)} sections")
        return results
    
    def _optimize_context(self, context: str, max_length: int = 8000) -> str:
        """
        Optimize context to fit within token limits while preserving important information.
        
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
        
    def _get_timestamp(self):
        """Get current timestamp for logging and file naming."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")