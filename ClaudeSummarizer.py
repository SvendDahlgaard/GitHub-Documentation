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
        preservation between sections. Handles large sections by splitting them.
        
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
            query = """Create detailed developer-focused documentation for this code section with the following structure:

    ## 1. QUICK OVERVIEW (10%)
    Briefly explain what this code does, its main purpose, and when/why it would be used.

    ## 2. IMPLEMENTATION DETAILS (60%)
    Provide a thorough, mechanical explanation of how the code works:

    - Detail each class with its purpose, attributes, and important methods
    - For significant methods, explain:
    * Parameters and return values
    * Function logic and algorithm details
    * Edge cases and error handling
    - Document important variables and data structures
    - Explain any non-trivial logic or algorithms
    - Describe how different components interact

    Focus on being specific and precise rather than abstract. Include actual method signatures, parameter names, and specific implementation details directly from the code.

    ## 3. USAGE EXAMPLES (30%)
    Provide multiple concrete code examples showing how to use this code:

    - Basic usage examples showing the most common patterns
    - More advanced examples demonstrating different features
    - Examples showing integration with other components
    - If applicable, show complete workflow examples

    Make examples practical, showing real-world usage scenarios rather than theoretical concepts.

    In your analysis, prioritize concrete implementation details and practical usage over architectural patterns or theoretical discussions. Developers should understand exactly how to use this code after reading your documentation."""
    
            
        analyses = {}
        accumulated_context = ""
        
        logger.info(f"Starting analysis of {len(sections)} sections with{' context' if use_context else 'out context'}")
        
        # Process sections sequentially
        for i, (section_name, files) in enumerate(sections):
            logger.info(f"Processing section {i+1}/{len(sections)}: {section_name} ({len(files)} files)")
            
            # Check if section is too large (rough estimation)
            estimated_tokens = sum(len(content) for content in files.values()) // 4
            
            # If section is very large, split it
            if estimated_tokens > 150000:  # Set a threshold below Claude's limit
                logger.info(f"Section {section_name} is large (est. {estimated_tokens} tokens), splitting for processing")
                # Create context to use if applicable
                context_to_use = None
                if use_context and accumulated_context:
                    context_to_use = f"Previously analyzed sections revealed: {accumulated_context}"
                result = self._process_large_section(section_name, files, query, context_to_use, use_context, accumulated_context, model, use_batch)
            else:
                # Format files for Claude
                section_content = self._format_files_for_claude(files)
                
                # Get context for this section if enabled
                context_to_use = None
                if use_context and accumulated_context:
                    context_to_use = f"Previously analyzed sections revealed: {accumulated_context}"
                
                # Enhance query with contextual guidance if we have context
                effective_query = query
                if context_to_use:
                    effective_query = f"{query}\n\nConsider these insights from other sections: {accumulated_context}"
                
                # Analyze the section
                result = self.analyze_with_claude(
                    content=section_content,
                    query=effective_query,
                    section_name=section_name,
                    context=context_to_use,
                    use_batch=use_batch,
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

    def _process_large_section(self, section_name: str, files: Dict[str, str], 
                            query: str, context_to_use: Optional[str], use_context: bool, 
                            accumulated_context: str, model: str, use_batch: bool) -> str:
        """
        Process a section that is too large for a single Claude request.
        Splits the section into file-based batches, analyzes each, then synthesizes the results.
        """
        logger.info(f"Processing large section {section_name} by splitting into manageable batches")
        
        # Group files into batches based on estimated token size
        batches = []
        current_batch = {}
        current_size = 0
        
        # Sort files by size (smallest first) for better packing
        CHARS_PER_TOKEN = 4
        sorted_files = sorted(files.items(), key=lambda x: len(x[1]))
        
        for path, file_content in sorted_files:
            # Estimate tokens for this file
            file_tokens = len(file_content) // CHARS_PER_TOKEN
            file_display = f"\n\n## File: {path}\n```\n{file_content}\n```\n"
            file_display_tokens = len(file_display) // CHARS_PER_TOKEN
            
            # If adding this file would exceed limit and we already have files in the batch
            if current_size + file_display_tokens > 100000 and current_batch:  # Conservative limit
                batches.append(current_batch)
                current_batch = {}
                current_size = 0
            
            # Handle files that are too large individually
            if file_display_tokens > 100000:
                logger.warning(f"File {path} is too large ({file_tokens} tokens), processing separately")
                # Create a batch with just this truncated file
                truncated_content = file_content[:400000] + "\n\n... [TRUNCATED: File too large to display completely]"
                batches.append({path: truncated_content})
            else:
                # Add file to current batch
                current_batch[path] = file_content
                current_size += file_display_tokens
        
        # Add the last batch if it has files
        if current_batch:
            batches.append(current_batch)
        
        logger.info(f"Split section {section_name} into {len(batches)} batches")
        
        # Process each batch
        batch_analyses = []
        
        for i, batch_files in enumerate(batches):
            batch_name = f"{section_name}_batch_{i+1}"
            logger.info(f"Processing {batch_name} with {len(batch_files)} files")
            
            # Format batch files for Claude
            batch_content = self._format_files_for_claude(batch_files)
            
            # Create batch-specific query
            batch_query = f"{query}\n\nThis is batch {i+1} of {len(batches)} for section '{section_name}'."
            if i > 0:
                batch_query += "\nBuild upon the analysis of previous batches without repeating information."
            
            # Get context for this batch
            batch_context = context_to_use if use_context else None
            if i > 0 and batch_analyses:
                # For later batches, add context from previous batch analyses
                previous_results = "\n\n".join(batch_analyses[:i])
                summary = f"Previous batches of this section contained: {previous_results[:4000]}..."
                batch_context = f"{context_to_use if context_to_use else ''}\n\n{summary}"
            elif use_context and accumulated_context and not context_to_use:
                batch_context = f"Previously analyzed sections revealed: {accumulated_context}"
            
            # KEY CHANGE: Use the _analyze_with_retry method from BaseClaudeService
            batch_result = self._analyze_with_retry(
                batch_content,
                batch_query,
                batch_name,
                batch_context,
                model,
                use_batch
            )
            
            # Add a delay between batches to avoid hitting rate limits
            if i < len(batches) - 1:
                time.sleep(20)  # Wait 20 seconds between batch processing
            
            # Store the batch result
            self._save_analysis(batch_name, batch_result)
            batch_analyses.append(batch_result)

            if i < len(batches) - 1:
                logger.info(f"Waiting 60 seconds before processing next batch to avoid rate limits...")
                time.sleep(60)  # Wait a full minute between batch processing

        logger.info(f"Waiting 60 seconds before final synthesis to avoid rate limits...")
        time.sleep(60)
        
        # If only one batch (which can happen when all files are processed individually),
        # just return that analysis
        if len(batch_analyses) == 1:
            return batch_analyses[0]
        
        # Otherwise, synthesize the results from all batches
        synthesis_content = {"analyses.md": "\n\n---\n\n".join(
            [f"## Batch {i+1}\n\n{analysis}" for i, analysis in enumerate(batch_analyses)]
        )}
        
        synthesis_query = f"""The following contains individual analyses of {len(batches)} batches from section '{section_name}' that was split due to size.
        
    Please synthesize these separate analyses into a single comprehensive analysis that covers the entire section. Focus on:
    1. The overall purpose and functionality of the section
    2. Key classes, functions, and design patterns across all batches
    3. How this section relates to the rest of the codebase
    4. Important implementation details and technical considerations

    The final analysis should be coherent and well-structured, avoiding redundancy while preserving all important insights from the individual batch analyses."""
        
        # Get the final synthesized analysis
        final_result = self._analyze_with_retry(
            content=synthesis_content,
            query=synthesis_query,
            section_name=f"{section_name}_synthesis",
            context=None,  # Don't need context for synthesis
            use_batch=False,  # Use direct API for synthesis as it's a simpler task
            model=model
        )
        
        # Save the synthesis
        self._save_analysis(f"{section_name}_synthesis", final_result)
        
        return final_result
    
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