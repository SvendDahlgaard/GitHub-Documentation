import os
import logging
import re
from typing import Dict, List, Tuple, Any, Optional

from ClaudeClientAPI import ClaudeAPIClient, OptimizedPromptManager

logger = logging.getLogger(__name__)

class BatchClaudeAnalyzer:
    """
    Class to analyze code using Claude AI via the Anthropic API with batch processing and prompt caching.
    This implementation offers significant cost savings through:
    1. Batch processing (50% discount)
    2. Prompt caching (90% discount on cache hits)
    3. Using Claude 3.5 Haiku for cost efficiency
    """
    
    def __init__(self, api_key=None, use_prompt_caching=True):
        """
        Initialize the batch Claude analyzer.
        
        Args:
            api_key: Claude API key (required)
            use_prompt_caching: Whether to use prompt caching for additional cost savings
        """
        # Initialize the core API client
        self.api_client = ClaudeAPIClient(api_key)
        self.use_prompt_caching = use_prompt_caching
    
    def _sanitize_custom_id(self, custom_id: str) -> str:
        """
        Sanitize a custom ID to ensure it meets Claude API requirements.
        Custom IDs must only contain alphanumeric characters, underscores, and hyphens.
        
        Args:
            custom_id: Original custom ID
            
        Returns:
            Sanitized custom ID that meets API requirements
        """
        # Replace any invalid characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', custom_id)
        
        # Ensure it's not longer than 64 characters
        if len(sanitized) > 64:
            sanitized = sanitized[:64]
            
        # Ensure it's not empty
        if not sanitized:
            sanitized = "section"
            
        return sanitized
        
    def analyze_sections_batch(self, sections: List[Tuple[str, Dict[str, str]]], 
                              query: Optional[str] = None, 
                              context_map: Optional[Dict[str, str]] = None, model: str = None) -> Dict[str, str]:
        """
        Analyze multiple code sections in a batch for optimal cost efficiency.
        
        Args:
            sections: List of (section_name, files) tuples
            query: Specific query about the code sections
            context_map: Optional map of section_name to context string
            model: Model for this specific batch
            
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
        
        # Create a mapping from sanitized section names to original ones
        sanitized_to_original = {}
        
        for section_name, files in sections:
            # Format the files for Claude
            files_content = ""
            for path, content in files.items():
                files_content += f"\n\n### File: {path}\n```\n{content}\n```\n"
            
            # Get context for this section if available
            section_context = context_map.get(section_name) if context_map else None
            
            # Create prompt with or without context
            if section_context:
                # Use the OptimizedPromptManager to create system blocks with caching if enabled
                system_blocks = OptimizedPromptManager.create_cached_system_prompt(
                    context=f"Previously, I've analyzed other sections of this codebase and discovered: \n\n{section_context}",
                    current_info=f"Now I'm analyzing the '{section_name}' section which contains these files:",
                    use_caching=self.use_prompt_caching
                )
                
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
            
            # Sanitize the custom_id to ensure it meets API requirements
            sanitized_id = self._sanitize_custom_id(section_name)
            sanitized_to_original[sanitized_id] = section_name
            
            # Create the batch request entry
            batch_requests.append({
                "custom_id": sanitized_id,
                "params": {
                    "model": model,
                    "max_tokens": 3000,
                    "system": system_blocks,
                    "messages": messages
                }
            })
        
        # Send the batch request using the API client
        batch_results = self.api_client.batch_request(batch_requests)
        
        # Map results back to original section names
        results = {}
        for sanitized_id, result in batch_results.items():
            original_name = sanitized_to_original.get(sanitized_id, sanitized_id)
            results[original_name] = result
            
        return results
    
    def _get_timestamp(self):
        """Get current timestamp for logging and file naming."""
        return self.api_client.get_timestamp()