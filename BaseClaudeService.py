import os
import backoff
import logging
import time
import requests as req  # Add this import
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class BaseClaudeService:
    """
    Base service for Claude API interactions, providing common functionality for 
    repository analysis components.
    """
    
    def __init__(self, batch_analyzer=None):
        """
        Initialize the base Claude service.
        
        Args:
            batch_analyzer: BatchClaudeAnalyzer instance for Claude API calls
        """
        self.batch_analyzer = batch_analyzer
    
    def _analyze_with_retry(self, content: Dict[str, str], query: str, 
                       section_name: str, context: Optional[str], 
                       model: str, use_batch: bool) -> str:
        """
        Wrapper for analyze_with_claude with exponential backoff for rate limiting.
        
        Args:
            content: Dictionary mapping file paths to contents
            query: Question to ask Claude about the content
            section_name: Name of the section (for logging)
            context: Optional context from previous analyses
            model: Claude model to use
            use_batch: Whether to use batch processing
            
        Returns:
            Analysis result from Claude
        """
        # Define backoff handler for rate limit errors
        @backoff.on_exception(
            backoff.expo,
            Exception,  # This is broad, but we'll filter in the giveup function
            max_tries=8,  # Maximum number of retries
            max_time=600,  # Maximum time to retry (10 minutes)
            giveup=lambda e: not (
                isinstance(e, Exception) and 
                hasattr(e, 'response') and 
                hasattr(e.response, 'status_code') and 
                e.response.status_code == 429
            ),
            on_backoff=lambda details: logger.warning(
                f"Rate limit hit. Retrying in {details['wait']:.1f} seconds... "
                f"(Attempt {details['tries']})"
            )
        )
        def _call_with_backoff():
            try:
                if use_batch:
                    # Format the section for Claude
                    section = [(section_name, content)]
                    
                    # Create context map if context provided
                    context_map = None
                    if context:
                        context_map = {section_name: context}
                    
                    # Send to Claude using batch analyzer
                    results = self.batch_analyzer.analyze_sections_batch(
                        sections=section,
                        query=query,
                        context_map=context_map,
                        model=model
                    )
                    
                    # Extract result
                    if results and section_name in results:
                        analysis = results[section_name]
                        return analysis
                    else:
                        raise Exception(f"No result returned for {section_name}")
                else:
                    # Use direct API
                    return self._analyze_with_direct_api(content, query, section_name, context, model)
            except Exception as e:
                # Log the exception
                if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 429:
                    logger.error(f"Rate limit exceeded: {str(e)}")
                    # Re-raise for backoff to catch
                    raise e
                # For other errors, just return an error message
                logger.error(f"Error in _call_with_backoff: {str(e)}")
                return f"Analysis failed: {str(e)}"
        
        try:
            # Call with backoff
            return _call_with_backoff()
        except Exception as e:
            logger.error(f"Final error after retries: {str(e)}")
            return f"Analysis failed after multiple retries: {str(e)}"

    # Update analyze_with_claude to use the retry mechanism
    def analyze_with_claude(self, 
                        content: Dict[str, str], 
                        query: str, 
                        section_name: str = "section",
                        context: Optional[str] = None,
                        model: str = "claude-3-5-haiku-20241022",
                        use_batch: bool = True,
                        batch_timeout: int = 300) -> str:
        """
        Send content to Claude for analysis with optional context and batch fallback.
        
        Args:
            content: Dictionary mapping file paths to contents
            query: Question to ask Claude about the content
            section_name: Name of the section (for logging)
            context: Optional context from previous analyses
            model: Claude model to use
            use_batch: Whether to use batch processing
            batch_timeout: Seconds to wait for batch before falling back to direct
            
        Returns:
            Analysis result from Claude
        """
        try:
            # Check if content is too large and split if necessary
            estimated_tokens = sum(len(content) for content in content.values()) // 4
            
            if estimated_tokens > 150000:  # Set a threshold below Claude's limit
                logger.info(f"Section {section_name} is large (est. {estimated_tokens} tokens), splitting into batches")
                
                # Split content into smaller batches
                content_batches = self._split_large_section(content)
                
                if len(content_batches) > 1:
                    logger.info(f"Split {section_name} into {len(content_batches)} batches")
                    
                    # Process each batch
                    all_results = []
                    for i, batch_content in enumerate(content_batches):
                        batch_name = f"{section_name}_batch_{i+1}"
                        logger.info(f"Processing {batch_name} with {len(batch_content)} files")
                        
                        # Add batch info to query
                        batch_query = f"{query}\n\nNote: This is batch {i+1} of {len(content_batches)} for section '{section_name}'."
                        
                        # If not the first batch, include context from previous analyses
                        batch_context = context
                        if i > 0 and all_results:
                            # Combine original context with results from previous batches
                            previous_results = "\n\n".join(all_results)
                            batch_context = f"{context if context else ''}\n\nResults from previous batches of this section: {previous_results}"
                        
                        # Analyze this batch with retry mechanism
                        result = self._analyze_with_retry(
                            batch_content, 
                            batch_query, 
                            batch_name, 
                            batch_context, 
                            model, 
                            use_batch
                        )
                        
                        all_results.append(result)
                    
                    # Combine results from all batches
                    # For the final batch, ask Claude to synthesize the full analysis
                    combined_content = {"summary.md": "\n\n".join(all_results)}
                    synthesis_query = f"""The following contains partial analyses of section '{section_name}' that was split into {len(content_batches)} batches due to size.
                    
    Please synthesize these partial analyses into a single coherent analysis that covers the entire section. Focus on:
    1. The overall purpose and functionality of the section
    2. Key classes, functions, and design patterns across all batches
    3. How this section relates to the rest of the codebase
    4. Important implementation details and technical considerations"""
                    
                    final_result = self._analyze_with_retry(
                        combined_content, 
                        synthesis_query, 
                        f"{section_name}_synthesis", 
                        None, 
                        model, 
                        False  # Use direct API for synthesis
                    )
                    
                    return final_result
                    
            # If we're not splitting, use the retry mechanism
            return self._analyze_with_retry(content, query, section_name, context, model, use_batch)
                
        except Exception as e:
            logger.error(f"Exception analyzing {section_name}: {str(e)}")
            return f"Analysis failed: {str(e)}"
            
    def _analyze_with_direct_api(self, content: Dict[str, str], query: str, 
                           section_name: str, context: Optional[str], 
                           model: str) -> str:
        """
        Use direct API calls instead of batching
        
        Args:
            content: Dictionary mapping file paths to contents
            query: Question to ask Claude about the content
            section_name: Name of the section
            context: Optional context from previous analyses
            model: Claude model to use
            
        Returns:
            Analysis result from Claude
        """
        logger.info(f"Using direct API for {section_name}")
        
        # Format content for Claude
        formatted_content = ""
        for path, file_content in content.items():
            formatted_content += f"\n\n# File: {path}\n```\n{file_content}\n```\n"
        
        # Create system message with context if available
        system_message = f"Analyze the code section named '{section_name}'."
        if context:
            system_message += f"\n\nPreviously, I've analyzed other sections and found: {context}"
        
        try:
            # Make direct API call using the appropriate client structure
            # Looking at your ClaudeClient.py, you need to use the headers and API directly
            
            data = {
                "model": model,
                "max_tokens": 3000,
                "system": system_message,
                "messages": [
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text",
                                "text": f"{formatted_content}\n\n{query}\n\nProvide a detailed but concise analysis."
                            }
                        ]
                    }
                ]
            }
            
            # Use the API client's headers for authentication
            response = req.post(
                "https://api.anthropic.com/v1/messages",
                headers=self.batch_analyzer.api_client.headers,
                json=data,
                timeout=120  # Increase timeout for direct API calls
            )
            
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return f"Analysis failed: API error {response.status_code}"
                
            # Parse the response
            response_data = response.json()
            content_blocks = response_data.get("content", [])
            
            # Extract text from content blocks
            text_content = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    text_content += block.get("text", "")
            
            return text_content
        except Exception as e:
            logger.error(f"Direct API call failed: {str(e)}")
            return f"Analysis failed: {str(e)}"
    
    def extract_context(self, analysis: str, max_size: int = 1500) -> str:
        """
        Extract the most relevant information from an analysis to use as context.
        Keeps it concise to avoid token limits.
        
        Args:
            analysis: The full analysis text
            max_size: Maximum character length for context
            
        Returns:
            Extracted context suitable for the next analysis
        """
        # Split by paragraphs or sections
        paragraphs = [p.strip() for p in analysis.split('\n\n') if p.strip()]
        
        # Prefer paragraphs that have key indicators of important insights
        key_indicators = ['purpose', 'main', 'functionality', 'core', 'responsible', 
                        'primary', 'key', 'important', 'essential', 'relates to']
        
        # Score paragraphs by relevance
        scored_paragraphs = []
        for p in paragraphs:
            score = 0
            for indicator in key_indicators:
                if indicator.lower() in p.lower():
                    score += 1
            scored_paragraphs.append((score, p))
        
        # Sort by score (highest first)
        scored_paragraphs.sort(reverse=True)
        
        # Take top paragraphs up to max_size
        context = ""
        for _, p in scored_paragraphs:
            if len(context) + len(p) + 2 <= max_size:  # +2 for newline
                context += p + "\n\n"
            else:
                break
                
        return context.strip()