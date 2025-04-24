import os
import logging
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
                          model: str = "claude-3-5-haiku-20241022") -> str:
        """
        Send content to Claude for analysis with optional context.
        
        Args:
            content: Dictionary mapping file paths to contents
            query: Question to ask Claude about the content
            section_name: Name of the section (for logging)
            context: Optional context from previous analyses
            model: Claude model to use
            
        Returns:
            Analysis result from Claude
        """
        try:
            # Format the section for Claude
            section = [(section_name, content)]
            
            # Create context map if context provided
            context_map = None
            if context:
                context_map = {section_name: context}
            
            # Send to Claude
            logger.info(f"Analyzing {section_name} with{' context' if context else ''}")
            results = self.batch_analyzer.analyze_sections_batch(
                sections=section,
                query=query,
                context_map=context_map,
                model=model
            )
            
            # Extract result
            if section_name in results:
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