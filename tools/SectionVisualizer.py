#!/usr/bin/env python3
"""
Visualization tool for comparing different section analysis methods.
This tool allows you to visualize how files are grouped in different section methods,
helping you understand the quality of each approach.
"""
import os
import sys
import json
import argparse
from collections import defaultdict

# Add parent directory to path to import modules
sys.path.append('..')

def load_section_data(input_file):
    """
    Load section data from a JSON file.
    
    Args:
        input_file: Path to JSON file with section data
        
    Returns:
        Dictionary of section data
    """
    try:
        with open(input_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading section data: {e}")
        return None

def create_html_visualization(section_data, output_file, title="Section Analysis Visualization"):
    """
    Create an HTML visualization of the section data.
    
    Args:
        section_data: Dictionary mapping section names to files
        output_file: Path to save HTML visualization
        title: Title for the visualization
    """
    # Count files in each section
    section_sizes = {section: len(files) for section, files in section_data.items()}
    
    # Create a file to section mapping for lookup
    file_to_sections = defaultdict(list)
    for section, files in section_data.items():
        for file in files:
            file_to_sections[file].append(section)
    
    # Create HTML content
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .stats {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .stat-box {{
            background: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin: 10px;
            min-width: 200px;
        }}
        .section-list {{
            background: #fff;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .section-header {{
            background: #e9ecef;
            padding: 10px 15px;
            border-radius: 5px 5px 0 0;
            cursor: pointer;
            position: relative;
        }}
        .section-header:hover {{
            background: #dee2e6;
        }}
        .section-header:after {{
            content: "+";
            position: absolute;
            right: 15px;
            top: 10px;
        }}
        .section-header.active:after {{
            content: "-";
        }}
        .section-content {{
            display: none;
            padding: 15px;
        }}
        .section-content.active {{
            display: block;
        }}
        .file-list {{
            list-style-type: none;
            padding-left: 0;
        }}
        .file-list li {{
            padding: 5px;
            border-bottom: 1px solid #f1f1f1;
        }}
        .file-list li:last-child {{
            border-bottom: none;
        }}
        .directory {{
            color: #0366d6;
        }}
        .search-box {{
            width: 100%;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }}
        .highlight {{
            background-color: #fffacd;
        }}
        .toolbar {{
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }}
        button {{
            padding: 8px 15px;
            margin: 5px;
            background: #4a6fa5;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
        button:hover {{
            background: #3a5a80;
        }}
        .section-size-indicator {{
            display: inline-block;
            min-width: 30px;
            text-align: center;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 12px;
            margin-left: 10px;
            background-color: #6c757d;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        
        <div class="stats">
            <div class="stat-box">
                <h3>Total Sections</h3>
                <p>{len(section_data)}</p>
            </div>
            <div class="stat-box">
                <h3>Average Files Per Section</h3>
                <p>{sum(section_sizes.values()) / len(section_sizes) if section_sizes else 0:.2f}</p>
            </div>
            <div class="stat-box">
                <h3>Largest Section</h3>
                <p>{max(section_sizes.values()) if section_sizes else 0} files</p>
            </div>
            <div class="stat-box">
                <h3>Smallest Section</h3>
                <p>{min(section_sizes.values()) if section_sizes else 0} files</p>
            </div>
        </div>
        
        <div class="toolbar">
            <div>
                <input type="text" id="searchInput" class="search-box" placeholder="Search for files or sections...">
            </div>
            <div>
                <button id="expandAll">Expand All</button>
                <button id="collapseAll">Collapse All</button>
                <button id="sortBySize">Sort by Size</button>
                <button id="sortByName">Sort by Name</button>
            </div>
        </div>
        
        <div id="sectionList" class="section-list">
"""
    
    # Add each section
    for section, files in sorted(section_data.items(), key=lambda x: x[0]):
        file_count = len(files)
        size_color = "#28a745" if file_count <= 10 else "#fd7e14" if file_count <= 20 else "#dc3545"
        
        html += f"""
            <div class="section-item" data-files="{file_count}" data-name="{section}">
                <div class="section-header">
                    {section} <span class="section-size-indicator" style="background-color: {size_color}">{file_count}</span>
                </div>
                <div class="section-content">
                    <ul class="file-list">
"""
        # Sort files by path
        for file in sorted(files):
            directory = os.path.dirname(file)
            filename = os.path.basename(file)
            html += f'                        <li><span class="directory">{directory}/</span>{filename}</li>\n'
        
        html += """
                    </ul>
                </div>
            </div>
"""
    
    # Close the HTML structure and add JavaScript
    html += """
        </div>
    </div>
    
    <script>
        // Toggle section content
        document.querySelectorAll('.section-header').forEach(header => {
            header.addEventListener('click', function() {
                this.classList.toggle('active');
                const content = this.nextElementSibling;
                content.classList.toggle('active');
            });
        });
        
        // Search functionality
        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            
            document.querySelectorAll('.section-item').forEach(section => {
                const sectionName = section.querySelector('.section-header').textContent.toLowerCase();
                const fileItems = section.querySelectorAll('.file-list li');
                let sectionVisible = false;
                
                // Check if section name matches
                if (sectionName.includes(searchTerm)) {
                    sectionVisible = true;
                    // Highlight all files since section matches
                    fileItems.forEach(item => {
                        item.style.display = '';
                        item.classList.remove('highlight');
                    });
                } else {
                    // Check individual files
                    let hasVisibleFiles = false;
                    
                    fileItems.forEach(item => {
                        const fileText = item.textContent.toLowerCase();
                        if (fileText.includes(searchTerm)) {
                            item.style.display = '';
                            item.classList.add('highlight');
                            hasVisibleFiles = true;
                        } else {
                            item.style.display = 'none';
                            item.classList.remove('highlight');
                        }
                    });
                    
                    sectionVisible = hasVisibleFiles;
                }
                
                // Show/hide section
                section.style.display = sectionVisible ? '' : 'none';
                
                // Expand section if visible and has search term
                if (sectionVisible && searchTerm) {
                    section.querySelector('.section-header').classList.add('active');
                    section.querySelector('.section-content').classList.add('active');
                } else if (!searchTerm) {
                    // Collapse when search is cleared
                    section.querySelector('.section-header').classList.remove('active');
                    section.querySelector('.section-content').classList.remove('active');
                }
            });
        });
        
        // Expand all sections
        document.getElementById('expandAll').addEventListener('click', function() {
            document.querySelectorAll('.section-header').forEach(header => {
                header.classList.add('active');
                header.nextElementSibling.classList.add('active');
            });
        });
        
        // Collapse all sections
        document.getElementById('collapseAll').addEventListener('click', function() {
            document.querySelectorAll('.section-header').forEach(header => {
                header.classList.remove('active');
                header.nextElementSibling.classList.remove('active');
            });
        });
        
        // Sort by size
        document.getElementById('sortBySize').addEventListener('click', function() {
            const sectionList = document.getElementById('sectionList');
            const sections = Array.from(sectionList.querySelectorAll('.section-item'));
            
            sections.sort((a, b) => {
                return parseInt(b.dataset.files) - parseInt(a.dataset.files);
            });
            
            sections.forEach(section => {
                sectionList.appendChild(section);
            });
        });
        
        // Sort by name
        document.getElementById('sortByName').addEventListener('click', function() {
            const sectionList = document.getElementById('sectionList');
            const sections = Array.from(sectionList.querySelectorAll('.section-item'));
            
            sections.sort((a, b) => {
                return a.dataset.name.localeCompare(b.dataset.name);
            });
            
            sections.forEach(section => {
                sectionList.appendChild(section);
            });
        });
    </script>
</body>
</html>
"""
    
    # Write the HTML file
    try:
        with open(output_file, 'w') as f:
            f.write(html)
        print(f"HTML visualization created: {output_file}")
        return True
    except Exception as e:
        print(f"Error creating HTML visualization: {e}")
        return False

def compare_methods(data_files, output_file):
    """
    Create a comparison visualization of different section methods.
    
    Args:
        data_files: Dictionary mapping method names to data files
        output_file: Path to save HTML visualization
    """
    method_data = {}
    all_files = set()
    
    # Load all data files
    for method, file_path in data_files.items():
        data = load_section_data(file_path)
        if data:
            method_data[method] = data
            # Collect all unique files
            for files in data.values():
                all_files.update(files)
    
    if not method_data:
        print("No valid data files to compare")
        return False
    
    # Create a comparison matrix
    # For each file, identify which section it belongs to in each method
    file_sections = {}
    for file in sorted(all_files):
        file_sections[file] = {}
        for method, sections in method_data.items():
            # Find which section contains this file
            for section, files in sections.items():
                if file in files:
                    file_sections[file][method] = section
                    break
    
    # Create HTML content
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Section Method Comparison</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
            position: sticky;
            top: 0;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .file-path {
            font-family: monospace;
            white-space: nowrap;
        }
        .section-name {
            background-color: #e9ecef;
            border-radius: 4px;
            padding: 2px 6px;
            display: inline-block;
        }
        .search-box {
            width: 100%;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        .stats {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .stat-box {
            background: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin: 10px;
            min-width: 200px;
        }
        .same-section {
            background-color: #e8f5e9;
        }
        .different-section {
            background-color: #fff3e0;
        }
        .toolbar {
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Section Method Comparison</h1>
        
        <div class="stats">
"""
    
    # Add statistics for each method
    for method, sections in method_data.items():
        section_count = len(sections)
        avg_size = sum(len(files) for files in sections.values()) / section_count if section_count else 0
        max_size = max(len(files) for files in sections.values()) if sections else 0
        
        html += f"""
            <div class="stat-box">
                <h3>{method}</h3>
                <p>Sections: {section_count}</p>
                <p>Avg Size: {avg_size:.2f}</p>
                <p>Max Size: {max_size}</p>
            </div>
"""
    
    html += """
        </div>
        
        <input type="text" id="searchInput" class="search-box" placeholder="Search for files or sections...">
        
        <table id="comparisonTable">
            <thead>
                <tr>
                    <th>File Path</th>
"""
    
    # Add column headers for each method
    for method in method_data.keys():
        html += f'                    <th>{method}</th>\n'
    
    html += """
                </tr>
            </thead>
            <tbody>
"""
    
    # Add a row for each file
    for file, sections in file_sections.items():
        # Check if this file is in the same section across all methods
        all_sections = list(sections.values())
        is_same_section = len(all_sections) > 1 and all(s == all_sections[0] for s in all_sections[1:])
        row_class = "same-section" if is_same_section else "different-section"
        
        html += f'                <tr class="{row_class}">\n'
        html += f'                    <td class="file-path">{file}</td>\n'
        
        # Add a column for each method
        for method in method_data.keys():
            section = sections.get(method, "")
            html += f'                    <td><span class="section-name">{section}</span></td>\n'
        
        html += '                </tr>\n'
    
    html += """
            </tbody>
        </table>
    </div>
    
    <script>
        // Search functionality
        const searchInput = document.getElementById('searchInput');
        const table = document.getElementById('comparisonTable');
        const rows = table.getElementsByTagName('tr');
        
        searchInput.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            
            // Loop through all table rows (skip header)
            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const filePath = row.cells[0].textContent.toLowerCase();
                
                // Check if the file path matches the search term
                let fileMatch = filePath.includes(searchTerm);
                
                // If not matched by file path, check sections
                if (!fileMatch) {
                    for (let j = 1; j < row.cells.length; j++) {
                        const sectionName = row.cells[j].textContent.toLowerCase();
                        if (sectionName.includes(searchTerm)) {
                            fileMatch = true;
                            break;
                        }
                    }
                }
                
                // Show or hide the row
                row.style.display = fileMatch ? '' : 'none';
            }
        });
    </script>
</body>
</html>"""
    
    # Write the HTML file
    try:
        with open(output_file, 'w') as f:
            f.write(html)
        print(f"Comparison visualization created: {output_file}")
        return True
    except Exception as e:
        print(f"Error creating comparison visualization: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Visualize section analysis results")
    parser.add_argument("--input", required=True, help="Input JSON file with section data")
    parser.add_argument("--output", default="section_visualization.html", 
                       help="Output HTML file (default: section_visualization.html)")
    parser.add_argument("--title", default="Section Analysis Visualization",
                       help="Title for the visualization")
    parser.add_argument("--compare", nargs='+', metavar=('METHOD=FILE'),
                       help="Compare multiple methods (format: method1=file1.json method2=file2.json)")
    
    args = parser.parse_args()
    
    if args.compare:
        # Process comparison arguments
        method_files = {}
        for arg in args.compare:
            if '=' in arg:
                method, file_path = arg.split('=', 1)
                method_files[method] = file_path
            else:
                print(f"Invalid format for --compare: {arg}. Expected method=file.json")
        
        if method_files:
            compare_methods(method_files, args.output)
        else:
            print("No valid comparison methods provided")
    else:
        # Process single file visualization
        section_data = load_section_data(args.input)
        if section_data:
            create_html_visualization(section_data, args.output, args.title)
        else:
            print(f"Failed to process section data from {args.input}")

if __name__ == "__main__":
    main()