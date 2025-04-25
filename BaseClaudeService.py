import os
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
            # If batching is disabled or we're processing a small section, use direct API
            if not use_batch:
                return self._analyze_with_direct_api(content, query, section_name, context, model)
                
            # Try batch processing first with a timeout
            start_time = time.time()
            
            # Format the section for Claude
            section = [(section_name, content)]
            
            # Create context map if context provided
            context_map = None
            if context:
                context_map = {section_name: context}
            
            # Send to Claude using batch analyzer with timeout tracking
            results = None
            try:
                results = self.batch_analyzer.analyze_sections_batch(
                    sections=section,
                    query=query,
                    context_map=context_map,
                    model=model,
                    timeout=batch_timeout
                )
            except TimeoutError:
                logger.warning(f"Batch processing timed out after {batch_timeout}s, falling back to direct API")
                return self._analyze_with_direct_api(content, query, section_name, context, model)
                
            # Extract result
            if results and section_name in results:
                analysis = results[section_name]
                
                # Check if we got an error
                if analysis.startswith("Error:"):
                    logger.error(f"Error analyzing {section_name}: {analysis}")
                    return f"Analysis failed: {analysis}"
                
                return analysis
            else:
                logger.error(f"No result returned for {section_name}")
                return "Analysis failed: No result returned"
                
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