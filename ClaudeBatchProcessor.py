import os
import logging
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
    
    def __init__(self, api_key=None, claude_model=None, use_prompt_caching=True):
        """
        Initialize the batch Claude analyzer.
        
        Args:
            api_key: Claude API key (required)
            claude_model: Claude model to use (defaults to Claude 3.5 Haiku for cost efficiency)
            use_prompt_caching: Whether to use prompt caching for additional cost savings
        """
        # Initialize the core API client
        self.api_client = ClaudeAPIClient(api_key)
        self.use_prompt_caching = use_prompt_caching
        self.claude_model = self.api_client.claude_model
        
    def analyze_sections_batch(self, sections: List[Tuple[str, Dict[str, str]]], model: str, 
                              query: Optional[str] = None, 
                              context_map: Optional[Dict[str, str]] = None) -> Dict[str, str]:
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
            
            # Create the batch request entry
            batch_requests.append({
                "custom_id": section_name,
                "params": {
                    "model": model,
                    "max_tokens": 3000,
                    "system": system_blocks,
                    "messages": messages
                }
            })
        
        # Send the batch request using the API client
        return self.api_client.batch_request(batch_requests)
    
    def _get_timestamp(self):
        """Get current timestamp for logging and file naming."""
        return self.api_client.get_timestamp()