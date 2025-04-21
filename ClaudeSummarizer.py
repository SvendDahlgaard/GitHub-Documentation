import os
import logging
import re
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

class ClaudeSummarizer:
    """
    Handles all Claude-related summarization and analysis functionality,
    including batch processing and context management between sections.
    """

    def __init__(self, batch_analyzer, output_dir = "analysis"):
        """
        Initialize the Claude summarizer.
        
        Args:
            batch_analyzer: BatchClaudeAnalyzer instance for efficient LLM queries
            output_dir: Directory to output analysis files
        """
        self.batch_analyzer = batch_analyzer
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def create_summaries_batch(self, sections, query, use_context = True, model = "claude-3-5-sonnet-20240307"):
         """
        Analyze all sections in a batch for efficiency.
        
        Args:
            sections: List of tuples (section_name, files)
            query: Question to ask Claude about each section
            use_context: Whether to use context from previous sections
            model: Claude model to use for analysis
            
        Returns:
            Dictionary mapping section names to analysis results
        """
         analyses = {}
         if not use_context:
             #Simple case: Anlyze all blocks in one bathc without context
             logger.info(f"Analyze all {len(sections)} sections in a single batch")
             try:
                 analyses = self.batch_analyzer.analyse_sections_batch(
                     sections = sections,
                     query = query,
                     model = model
                 )
                 logger.info(f"Successfully analyzed {len(sections)} sections in a single batch")
             except Exception as e:
                 logger.error(f"Exception in analyze_sections_batch: {type(e).__name__}: {str(e)}") 
                 import traceback 
                 traceback.print_exc()
                 raise
         else: 
            # More complex case: analyze in chunks to maintain context between groups
            # Group sections into chunks of 5-10 for efficient batching while maintaining context flow
            chunk_size = 5
            sections_chunks = [sections[i:i+chunk_size] for i in range(0, len(sections), chunk_size)]

            context_map = {}
            context = ""

            for chunk_idx, chunk in enumerate(sections_chunks):
                logger.info(f"Processing batch chunk {chunk_idx+1}/{len(sections_chunks)} ({len(chunk)} sections)")

                # Prepare context for each section in this chunk
                for section_name, _ in chunk:
                    context_map[section_name] = context.strip()

                # Process this chunk as a batch
                chunk_results = self.batch_analyzer.analyze_sections_batch(
                    chunk, 
                    query=query, 
                    context_map=context_map, 
                    model=model
                )
                analyses.update(chunk_results)

                # Update context for the next chunk
                for section_name, section_files in chunk:
                    if section_name in chunk_results:
                        analysis = chunk_results[section_name]

                        # Save individual section analysis
                        section_filename = section_name.replace('/', '_').replace('\\', '_')
                        with open(os.path.join(self.output_dir, f"{section_filename}.md"), "w") as f:
                            f.write(f"# {section_name}\n\n")
                            f.write(analysis)
                        
                        # Extract key points for context
                        key_points = self._extract_key_points(analysis)
                        context += f"\n\nSection '{section_name}':\n{key_points}\n"
                        # Keep context from getting too large
                        context = context[-10000:] if len(context) > 10000 else context
         return analyses
    def _extract_key_points(self, text, max_points=5):
        """
        Extract key points from analysis for context.
        
        Args:
            text: The analysis text to extract key points from
            max_points: Maximum number of key points to extract
            
        Returns:
            String with extracted key points
        """
        # Simple extraction of sentences with key indicators
        key_sentences = []
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Simple extraction of sentences with key indicators
        key_sentences = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Look for sentences with indicators of importance
        indicators = ['main', 'primary', 'key', 'core', 'critical', 'essential', 'important']
        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in indicators):
                key_sentences.append(sentence)
                
            if len(key_sentences) >= max_points:
                break
                
        # If not enough key sentences found, take first few sentences
        if len(key_sentences) < 3:
            key_sentences = sentences[:5]
            
        return " ".join(key_sentences)
    



         