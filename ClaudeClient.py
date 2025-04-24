import os
import json
import time
import logging
import requests as req  
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ClaudeAPIClient:
    """
    Base client for interacting with Claude API with optimization features.
    This client provides core functionality for both individual and batch requests.
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the Claude API client.
        
        Args:
            api_key: Claude API key (if None, tries to read from environment)
        """
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("Claude API key is required. Set it in .env file or pass directly.")
            

        # Standard headers for API requests
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Validate API key with a simple test
        try:
            self._test_api_connection()
            logger.info("Successfully connected to Anthropic API")
        except Exception as e:
            logger.error(f"Failed to connect to Anthropic API: {e}")
            raise
    
    def _test_api_connection(self):
        """Test the API connection with a simple request."""
        test_model = "claude-3-5-haiku-20241022"
        data = {
            "model": test_model,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hello, this is a test."}]
        }
        
        response = req.post(
            "https://api.anthropic.com/v1/messages",
            headers=self.headers,
            json=data,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"API connection test failed: {response.status_code} - {response.text}")

    def batch_request(self, request_list: List[Dict]) -> Dict[str, Any]:
        """
        Send a batch of requests to the Anthropic API.
        
        Args:
            requests: List of request objects with format:
                     {
                       "custom_id": "unique_id",
                       "params": { ... request parameters ... }
                     }
            
        Returns:
            Dictionary mapping custom_ids to results
        """
        try:
            # Create batch
            logger.info(f"Creating batch with {len(request_list)} requests")
            
            # Use the renamed module
            create_response = req.post(  # Use req instead of requests
                "https://api.anthropic.com/v1/messages/batches",
                headers=self.headers,
                json={"requests": request_list},  # Use the renamed parameter
                timeout=30
            )
            
            if create_response.status_code != 200:
                logger.error(f"Failed to create batch: {create_response.status_code} - {create_response.text}")
                raise Exception(f"Failed to create batch: {create_response.text}")
            
            batch_data = create_response.json()
            batch_id = batch_data.get("id")
            logger.info(f"Successfully created batch with ID: {batch_id}")
            
            # Poll for batch completion
            return self._poll_batch_status(batch_id)
            
        except Exception as e:
            logger.error(f"Error in batch request: {e}")
            return {}
    
    def _poll_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Poll for batch completion and retrieve results.
        
        Args:
            batch_id: The batch ID to poll
            
        Returns:
            Dictionary mapping custom_ids to results
        """
        max_polls = 120  # Maximum number of polling attempts
        initial_poll_interval = 2  # Start with 2 seconds
        max_poll_interval = 15  # Maximum interval of 15 seconds
        current_interval = initial_poll_interval
        
        for i in range(max_polls):
            logger.info(f"Polling batch status (attempt {i+1}, interval: {current_interval}s)...")
            
            status_response = req.get(
                f"https://api.anthropic.com/v1/messages/batches/{batch_id}",
                headers=self.headers,
                timeout=30
            )
            
            if status_response.status_code != 200:
                logger.error(f"Failed to get batch status: {status_response.status_code} - {status_response.text}")
                # Use exponential backoff for errors
                time.sleep(min(current_interval * 2, 60))
                current_interval = min(current_interval * 2, 60)
                continue
            
            status_data = status_response.json()
            processing_status = status_data.get("processing_status")
            request_counts = status_data.get("request_counts", {})
            
            # Calculate progress percentage
            total_requests = sum(request_counts.values())
            completed_requests = request_counts.get("completed", 0) + request_counts.get("failed", 0)
            progress = (completed_requests / total_requests * 100) if total_requests > 0 else 0
            
            logger.info(f"Batch status: {processing_status}, Progress: {progress:.1f}% ({completed_requests}/{total_requests})")
            
            # Check if batch has ended
            if processing_status == "ended":
                results_url = status_data.get("results_url")
                if results_url:
                    return self._retrieve_batch_results(results_url)
                else:
                    logger.error("Batch ended but no results URL provided")
                    return {}
            
            # Check if any requests are in progress
            in_progress = request_counts.get("in_progress", 0)
            if in_progress > 0:
                # If requests are actively being processed, poll more frequently
                current_interval = max(initial_poll_interval, current_interval / 2)
            else:
                # If just waiting in queue, gradually increase polling interval
                current_interval = min(current_interval * 1.5, max_poll_interval)
            
            # Wait before polling again with variable interval
            time.sleep(current_interval)
        
        logger.error(f"Batch processing timed out after {max_polls} polling attempts")
        return {}
    
    def _retrieve_batch_results(self, results_url: str) -> Dict[str, str]:
        """
        Retrieve and process batch results.
        
        Args:
            results_url: URL to retrieve batch results
            
        Returns:
            Dictionary mapping custom_ids to text content
        """
        logger.info(f"Retrieving batch results from: {results_url}")
        
        response = req.get(results_url, headers=self.headers, timeout=60)
        
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
                    logger.error(f"Error processing item '{custom_id}': {error_type} - {error_message}")
                    results[custom_id] = f"Error: {error_message}"
            except json.JSONDecodeError:
                logger.error(f"Failed to parse result line: {line}")
        
        logger.info(f"Successfully retrieved results for {len(results)} items")
        return results
        
    def get_timestamp(self):
        """Get current timestamp for logging and file naming."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class OptimizedPromptManager:
    """
    Helper class for managing prompt optimizations like context pruning and caching.
    """
    
    @staticmethod
    def create_cached_system_prompt(context: str, current_info: str, use_caching: bool = True) -> List[Dict]:
        """
        Create system prompt blocks with optional caching for context.
        
        Args:
            context: Previous context that can be cached
            current_info: Current information (not cached)
            use_caching: Whether to use caching
            
        Returns:
            List of system prompt blocks
        """
        if not context:
            return [{"type": "text", "text": current_info}]
            
        if use_caching:
            return [
                {
                    "type": "text",
                    "text": context,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": current_info
                }
            ]
        else:
            return [{"type": "text", "text": f"{context}\n\n{current_info}"}]
    
    @staticmethod
    def optimize_context(context: str, max_length: int = 8000) -> str:
        """
        Optimize context to fit within token limits while preserving important information.
        
        Args:
            context: The context to optimize
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
    
    @staticmethod
    def extract_json(text: str) -> str:
        """
        Extract JSON from Claude's response text.
        
        Args:
            text: Response text from Claude
            
        Returns:
            Extracted JSON string
        """
        # Try to find JSON within ```json ... ``` blocks
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if json_match:
            return json_match.group(1)
        
        # Try to find JSON within any ``` ... ``` blocks
        code_match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if code_match:
            return code_match.group(1)
        
        # Look for JSON-like structures with { ... }
        brace_match = re.search(r'(\{[\s\S]*\})', text)
        if brace_match:
            return brace_match.group(1)
        
        # Default to returning the whole text
        return text