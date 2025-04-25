import os
import logging
import time
from typing import List, Dict, Tuple, Any, Optional
from BaseClaudeService import BaseClaudeService

logger = logging.getLogger(__name__)

class ClaudeSummarizer(BaseClaudeService):
    """
    Handles Claude-based summarization of code sections with context preservation
    between sections.
    """

    def __init__(self, batch_analyzer, output_dir="analysis"):
        """
        Initialize the Claude summarizer.
        
        Args:
            batch_analyzer: BatchClaudeAnalyzer instance for Claude API calls
            output_dir: Base directory for output files
        """
        super().__init__(batch_analyzer)
        self.base_output_dir = output_dir
        self.current_output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def set_output_directory(self, repo_output_dir: str):
        """
        Set the repository-specific output directory.
        
        Args:
            repo_output_dir: Repository-specific output directory
        """
        self.current_output_dir = repo_output_dir
        os.makedirs(repo_output_dir, exist_ok=True)
        
    def create_section_summaries(self, 
                               sections: List[Tuple[str, Dict[str, str]]], 
                               query: str = None,
                               use_context: bool = True,
                               use_batch: bool = True,
                               model: str = "claude-3-5-haiku-20241022") -> Dict[str, str]:
        """
        Create comprehensive summaries for each section, with optional context
        preservation between sections.
        
        Args:
            sections: List of tuples (section_name, files)
            query: Question to ask Claude about each section
            use_context: Whether to use insights from previous sections as context
            model: Claude model to use
            
        Returns:
            Dictionary mapping section names to summaries
        """
        # Default query if none provided
        if not query:
            query = "Analyze this section of code. Explain its purpose, key components, and how it fits into the larger codebase."
            
        analyses = {}
        accumulated_context = ""
        
        logger.info(f"Starting analysis of {len(sections)} sections with{' context' if use_context else 'out context'}")
        
        # Process sections sequentially
        for i, (section_name, files) in enumerate(sections):
            logger.info(f"Processing section {i+1}/{len(sections)}: {section_name} ({len(files)} files)")
            
            # Format files for Claude
            section_content = self._format_files_for_claude(files)
            
            # Get context for this section if enabled
            context = None
            if use_context and accumulated_context:
                context = f"Previously analyzed sections revealed: {accumulated_context}"
            
            # Enhance query with contextual guidance if we have context
            effective_query = query
            if context:
                effective_query = f"{query}\n\nConsider these insights from other sections: {accumulated_context}"
            
            # Analyze the section
            result = self.analyze_with_claude(
                content=section_content,
                query=effective_query,
                section_name=section_name,
                context=context,
                use_batch= use_batch,
                model=model
            )
            
            # Store the result
            analyses[section_name] = result
            
            # Save to file in the repository-specific directory
            self._save_analysis(section_name, result)
            
            # Update accumulated context if this wasn't an error
            if not result.startswith("Analysis failed:") and use_context:
                context_extract = self.extract_context(result)
                accumulated_context += f"\n\n{section_name}: {context_extract}"
                # Keep context from getting too large
                if len(accumulated_context) > 6000:
                    accumulated_context = accumulated_context[-6000:]
            
            # Small delay between requests to avoid rate limiting
            if i < len(sections) - 1:
                time.sleep(1)
                
        logger.info(f"Completed analysis of {len(sections)} sections")
        return analyses
    
    def _format_files_for_claude(self, files: Dict[str, str]) -> Dict[str, str]:
        """
        Format files in a way that's optimal for Claude to analyze.
        
        Args:
            files: Dictionary mapping file paths to contents
            
        Returns:
            Dictionary with formatted content
        """
        formatted_output = {}
        
        # Create a combined file listing with syntax highlighting
        files_content = ""
        for path, content in files.items():
            # Determine file extension for syntax highlighting
            ext = os.path.splitext(path)[1].lower()
            
            # Map common extensions to language for syntax highlighting
            lang = ""
            if ext in ['.py', '.pyw']:
                lang = "python"
            elif ext in ['.js', '.jsx', '.ts', '.tsx']:
                lang = "javascript"
            elif ext in ['.html', '.htm']:
                lang = "html"
            elif ext in ['.css']:
                lang = "css"
            elif ext in ['.json']:
                lang = "json"
            elif ext in ['.md', '.markdown']:
                lang = "markdown"
            elif ext in ['.c', '.cpp', '.h', '.hpp']:
                lang = "cpp"
            elif ext in ['.java']:
                lang = "java"
            elif ext in ['.rb']:
                lang = "ruby"
            
            # Add the file with syntax highlighting
            files_content += f"\n\n## File: {path}\n```{lang}\n{content}\n```\n"
        
        formatted_output["code_files.md"] = f"# Code Files\n{files_content}"
        return formatted_output
    
    def _save_analysis(self, section_name: str, analysis: str) -> None:
        """
        Save a section analysis to a markdown file in the current output directory.
        
        Args:
            section_name: Name of the section
            analysis: Analysis result to save
        """
        try:
            # Create a safe filename
            section_filename = section_name.replace('/', '_').replace('\\', '_')
            filepath = os.path.join(self.current_output_dir, f"{section_filename}.md")
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {section_name}\n\n")
                f.write(analysis)
                
            logger.info(f"Saved analysis for '{section_name}' to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save analysis for '{section_name}': {str(e)}")