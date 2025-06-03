"""
This module provides functions to convert Gutenberg HTML books with images
into the riverst JSON format. It's designed to handle various HTML structures
from Project Gutenberg.
"""

import re
import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
from bs4 import BeautifulSoup, Tag, NavigableString

# Import click conditionally to allow running without it
try:
    import click
except ImportError:
    click = None


# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_vocab_words(text: str, max_words: int = 5) -> List[str]:
    """
    Extract potential vocabulary words from text.
    
    Args:
        text: The text to extract vocabulary words from
        max_words: Maximum number of words to extract
        
    Returns:
        List of vocabulary words
    """
    # Find all words of 7+ characters
    words = re.findall(r'\b[A-Za-z]{7,}\b', text)
    words = [w.lower() for w in words]
    
    # Count occurrences to find uncommon words
    word_counts = Counter(words)
    
    # Sort by frequency (ascending) to get the less common words first
    # For words with the same frequency, sort by length (descending) to get longer words
    sorted_words = sorted(word_counts.items(), key=lambda x: (x[1], -len(x[0])))
    
    # Extract the top words
    return [word for word, _ in sorted_words[:max_words]]


def setup_output_directories(output_dir: str, book_title: str) -> str:
    """
    Create the necessary directory structure for the book.
    
    Args:
        output_dir: Base directory for books
        book_title: Title of the book
        
    Returns:
        Path to the book directory
    """
    # Create directory name from title
    book_dir_name = book_title.lower().replace(" ", "_").replace(":", "_").replace(";", "_").replace("/", "_")
    book_dir = os.path.join(output_dir, book_dir_name)
    
    # Create directories
    os.makedirs(book_dir, exist_ok=True)
    os.makedirs(os.path.join(book_dir, "audios"), exist_ok=True)
    os.makedirs(os.path.join(book_dir, "images"), exist_ok=True)
    
    return book_dir


def is_introduction_or_preface(text: str) -> bool:
    """
    Detect if a section is an introduction, preface, or front matter.
    
    Args:
        text: Section title or text to check
        
    Returns:
        True if the section appears to be introductory material
    """
    intro_patterns = [
        r'(?i)introduction',
        r'(?i)preface', 
        r'(?i)foreword',
        r'(?i)author\'s note',
        r'(?i)bibliographical',
        r'(?i)dedication',
        r'(?i)copyright',
        r'(?i)contents',
        r'(?i)editorial note',
        r'(?i)translator\'s note',
        r'(?i)epigraph',
        r'(?i)illustrations'
    ]
    
    return any(re.search(pattern, text) for pattern in intro_patterns)


def extract_title_author(soup: BeautifulSoup) -> Tuple[str, str]:
    """
    Extract the title and author from the HTML.
    
    Args:
        soup: BeautifulSoup object of the HTML
        
    Returns:
        Tuple containing (title, author)
    """
    title = "Unknown Book"
    author = "Unknown Author"
    
    # Try to get title from meta tag
    title_meta = soup.find('title')
    if title_meta:
        title_text = title_meta.text
        # Format: "Title of the Book | Project Gutenberg" or "The Project Gutenberg eBook of Title, by Author"
        if " | Project Gutenberg" in title_text:
            title = title_text.split(" | Project Gutenberg")[0].strip()
        else:
            title_match = re.search(r'of ([^,]+)(?:, by (.+))?', title_text)
            if title_match:
                title = title_match.group(1).strip()
                if title_match.group(2):
                    author = title_match.group(2).strip()
    
    # If no author found, try to find it in the body
    if author == "Unknown Author":
        author_elem = soup.find(['h1', 'h2', 'h3'], string=lambda s: s and 'by' in s.lower())
        if author_elem:
            author_match = re.search(r'by ([^,]+)', author_elem.text, re.IGNORECASE)
            if author_match:
                author = author_match.group(1).strip()
    
    return title, author


def find_contents_section(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Find the table of contents section in the HTML.
    
    Args:
        soup: BeautifulSoup object of the HTML
        
    Returns:
        The contents section tag or None if not found
    """
    # Strategy 1: Look for a heading with "Contents"
    contents_heading = soup.find(['h1', 'h2', 'h3'], 
                                 string=lambda s: s and re.search(r'\bContents\b', s, re.IGNORECASE))
    
    if contents_heading:
        logger.info("Found contents heading")
        return contents_heading
    
    # Strategy 2: Look for a div with class="contents"
    contents_div = soup.find('div', class_='contents')
    if contents_div:
        logger.info("Found contents div with class='contents'")
        return contents_div
    
    # Strategy 3: Look for a div containing chapter links
    potential_divs = soup.find_all('div')
    for div in potential_divs:
        chapter_links = div.find_all('a', class_='pginternal')
        if len(chapter_links) > 3:  # Assuming a valid table of contents has multiple chapters
            logger.info("Found div with multiple chapter links")
            return div
    
    logger.warning("Could not find contents section")
    return None


def extract_chapter_links(contents_section: Tag) -> List[Tuple[str, str, str]]:
    """
    Extract chapter links from the contents section.
    
    Args:
        contents_section: The tag containing the table of contents
        
    Returns:
        List of (chapter_id, chapter_number, chapter_title) tuples
    """
    chapter_links = []
    
    # Strategy 1: Find a table within the contents section
    table = contents_section.find('table')
    if table:
        logger.info("Found chapter links in table")
        rows = table.find_all('tr')
        
        for row in rows:
            # Look for links in this row
            link = row.find('a', class_='pginternal')
            if not link:
                continue
                
            href = link.get('href')
            if href and href.startswith('#'):
                chapter_id = href.lstrip('#')
                link_text = link.get_text(strip=True)
                
                # Extract chapter number and title
                chapter_number = ""
                chapter_title = link_text
                
                # Check if the link text contains both number and title
                chapter_match = re.search(r'(?:CHAPTER|Chapter)\s+([IVXLCDM\d]+)\.?\s*(.+)?', link_text)
                if chapter_match:
                    chapter_number = chapter_match.group(1)
                    if chapter_match.group(2):
                        chapter_title = chapter_match.group(2).strip()
                
                # Look for the title in a separate cell
                # If there's a sibling TD with the title
                cells = row.find_all('td')
                if len(cells) > 1:
                    for i, cell in enumerate(cells):
                        if link in cell.descendants and i+1 < len(cells):
                            title_cell = cells[i+1]
                            title_text = title_cell.get_text(strip=True)
                            if title_text:
                                chapter_title = title_text
                
                # Add to list of chapters
                logger.debug(f"Found chapter: id={chapter_id}, number={chapter_number}, title={chapter_title}")
                chapter_links.append((chapter_id, chapter_number, chapter_title))
    
    # Strategy 2: Look for links directly in the contents section
    if not chapter_links:
        logger.info("Looking for chapter links directly in contents section")
        links = contents_section.find_all('a', class_='pginternal')
        
        # Check if we're dealing with a div.contents structure like in Christmas Carol
        is_contents_div = contents_section.name == 'div' and 'contents' in contents_section.get('class', [])
        
        for link in links:
            href = link.get('href')
            if href and href.startswith('#'):
                chapter_id = href.lstrip('#')
                
                # Get the text before the link (could be chapter number)
                prev_text = ""
                prev_elem = link.previous_sibling
                while prev_elem and isinstance(prev_elem, NavigableString):
                    prev_text = prev_elem.strip() + " " + prev_text
                    prev_elem = prev_elem.previous_sibling
                
                prev_text = prev_text.strip()
                
                # Get the link text (usually the chapter title)
                link_text = link.get_text(strip=True)
                
                # Extract chapter number and title
                chapter_number = ""
                chapter_title = link_text
                
                # Special handling for div.contents format (like Christmas Carol)
                if is_contents_div:
                    # Look for patterns like "STAVE I" or "STAVE 1" in the previous text
                    stave_match = re.search(r'(STAVE|Chapter)\s+([IVXLCDM\d]+)', prev_text, re.IGNORECASE)
                    if stave_match:
                        chapter_number = stave_match.group(2)
                
                # Try to extract chapter number from previous text for other formats
                if not chapter_number:
                    number_match = re.search(r'(?:CHAPTER|Chapter|STAVE)\s+([IVXLCDM\d]+)', prev_text, re.IGNORECASE)
                    if number_match:
                        chapter_number = number_match.group(1)
                
                # If no number found and link text has format "Chapter X. Title"
                if not chapter_number:
                    chapter_match = re.search(r'(?:CHAPTER|Chapter)\s+([IVXLCDM\d]+)\.?\s*(.+)?', link_text, re.IGNORECASE)
                    if chapter_match:
                        chapter_number = chapter_match.group(1)
                        if chapter_match.group(2):
                            chapter_title = chapter_match.group(2).strip()
                
                logger.debug(f"Found chapter: id={chapter_id}, number={chapter_number}, title={chapter_title}")
                chapter_links.append((chapter_id, chapter_number, chapter_title))
    
    # Strategy 3: Look for links in a pre tag
    if not chapter_links and contents_section.find('pre'):
        logger.info("Found chapter links in pre tag")
        pre_tag = contents_section.find('pre')
        links = pre_tag.find_all('a', class_='pginternal')
        
        for link in links:
            href = link.get('href')
            if href and href.startswith('#'):
                chapter_id = href.lstrip('#')
                link_text = link.get_text(strip=True)
                
                # Get the text before the link (often contains chapter number)
                prev_text = ""
                prev_elem = link.previous_sibling
                while prev_elem and isinstance(prev_elem, NavigableString):
                    prev_text = prev_elem.strip() + " " + prev_text
                    prev_elem = prev_elem.previous_sibling
                
                prev_text = prev_text.strip()
                
                # Extract chapter number and title
                chapter_number = ""
                chapter_title = link_text
                
                # Look for number in format "1. "
                number_match = re.search(r'(\d+)\.', prev_text)
                if number_match:
                    chapter_number = number_match.group(1)
                
                chapter_links.append((chapter_id, chapter_number, chapter_title))
    
    logger.info(f"Found {len(chapter_links)} chapter links")
    return chapter_links


def extract_chapter_content(soup: BeautifulSoup, chapter_id: str, next_chapter_id: Optional[str] = None) -> str:
    """
    Extract the content of a chapter.
    
    Args:
        soup: BeautifulSoup object of the HTML
        chapter_id: ID of the chapter to extract
        next_chapter_id: ID of the next chapter (to know where to stop)
        
    Returns:
        The chapter text
    """
    # Find the element with the chapter ID
    chapter_elem = soup.find(id=chapter_id)
    if not chapter_elem:
        logger.warning(f"Could not find chapter with id '{chapter_id}'")
        return ""
    
    # Find the chapter heading
    if chapter_elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        start_elem = chapter_elem
    else:
        # If the ID is not on a heading, it might be on a div or other container
        # Try to find the nearest heading within this element or its parents
        heading = chapter_elem.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if heading:
            start_elem = heading
        else:
            # Try to find a heading that precedes this element
            start_elem = chapter_elem.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if not start_elem:
                start_elem = chapter_elem
    
    # Determine the chapter container and boundaries
    chapter_container = None
    
    # Check if the chapter is inside a div.chapter container
    parent_div = chapter_elem.parent
    while parent_div:
        if parent_div.name == 'div' and 'chapter' in parent_div.get('class', []):
            chapter_container = parent_div
            break
        parent_div = parent_div.parent
    
    # Find the next chapter element to know where to stop
    next_chapter_elem = None
    if next_chapter_id:
        next_chapter_elem = soup.find(id=next_chapter_id)
    
    # Collect content elements
    content_elements = []
    
    # Strategy 1: If we have a chapter container, collect all paragraphs inside it
    if chapter_container:
        # Start collecting content after the chapter heading
        started = False
        for elem in chapter_container.find_all(['p', 'img', 'div', 'pre', 'table']):
            # Skip elements before the start_elem
            if not started:
                if elem == start_elem or is_element_after(elem, start_elem):
                    started = True
                else:
                    continue
            
            if elem.name == 'p':
                content_elements.append(elem.get_text(strip=True))
            elif elem.name == 'img':
                src = elem.get('src', '')
                if src:
                    content_elements.append(f"[Image: {src}]")
            elif elem.name == 'pre':
                # Handle preformatted text (poems, etc.)
                content_elements.append(elem.get_text(strip=True))
            elif elem.name == 'div' and 'poem' in elem.get('class', []):
                # Handle poem divs
                content_elements.append(elem.get_text(strip=True))
    
    # Strategy 2: If no chapter container or no content found, use sequential traversal
    if not chapter_container or not content_elements:
        current = start_elem.find_next()
        
        while current and current != next_chapter_elem:
            # Stop if we've found a new chapter heading without an explicit next_chapter_id
            if not next_chapter_id and current.name in ['h1', 'h2', 'h3'] and \
               re.search(r'(?:CHAPTER|Chapter|STAVE)\s+[IVXLCDM\d]+', current.get_text(strip=True), re.IGNORECASE):
                break
            
            # Process content
            if current.name == 'p':
                content_elements.append(current.get_text(strip=True))
            elif current.name == 'img':
                src = current.get('src', '')
                if src:
                    content_elements.append(f"[Image: {src}]")
            elif current.name == 'pre':
                content_elements.append(current.get_text(strip=True))
            elif current.name == 'div' and 'poem' in current.get('class', []):
                content_elements.append(current.get_text(strip=True))
            
            # Special handling for Alice in Wonderland format and others
            elif current.name == 'div' and (current.find('p') or current.find('img')):
                # Process children of the div instead of the div itself
                for child in current.find_all(['p', 'img']):
                    if child.name == 'p':
                        content_elements.append(child.get_text(strip=True))
                    elif child.name == 'img':
                        src = child.get('src', '')
                        if src:
                            content_elements.append(f"[Image: {src}]")
            
            # Move to the next element
            next_elem = current.find_next()
            if not next_elem:
                break
            current = next_elem
    
    # Filter out empty content and join with proper spacing
    chapter_text = "\n\n".join([p for p in content_elements if p and p.strip()])
    
    return chapter_text


def is_element_after(elem1: Tag, elem2: Tag) -> bool:
    """
    Check if elem1 comes after elem2 in the document.
    
    Args:
        elem1: First element
        elem2: Second element
        
    Returns:
        True if elem1 comes after elem2
    """
    # Convert elements to their string representation in the document
    elem1_str = str(elem1)
    elem2_str = str(elem2)
    
    # Get the full document as a string
    doc_str = str(elem1.parent)
    
    # Find the positions of both elements
    pos1 = doc_str.find(elem1_str)
    pos2 = doc_str.find(elem2_str)
    
    # Check if elem1 comes after elem2
    return pos1 > pos2


def is_element_inside(element: Tag, container: Tag) -> bool:
    """
    Check if an element is inside a container element.
    
    Args:
        element: The element to check
        container: The container element
        
    Returns:
        True if element is inside container
    """
    parent = element.parent
    while parent:
        if parent == container:
            return True
        parent = parent.parent
    return False


def identify_chapter_pattern(soup: BeautifulSoup) -> str:
    """
    Identify the chapter pattern used in the HTML document.
    
    Args:
        soup: BeautifulSoup object of the HTML
        
    Returns:
        String indicating the pattern: 'toc', 'divs', 'headers', or 'unknown'
    """
    # Check if there's a table of contents section with chapter links
    contents_section = find_contents_section(soup)
    if contents_section:
        links = contents_section.find_all('a', class_='pginternal')
        if len(links) > 2:
            return 'toc'
    
    # Check for div.chapter pattern
    chapter_divs = soup.find_all('div', class_='chapter')
    if len(chapter_divs) > 2:
        return 'divs'
    
    # Check for chapter headers pattern
    chapter_headers = soup.find_all(['h1', 'h2', 'h3'], string=lambda s: s and (
        re.search(r'(?:CHAPTER|Chapter|STAVE)\s+[IVXLCDM\d]+', s, re.IGNORECASE) or
        re.search(r'^(?:CHAPTER|Chapter|STAVE)\s+\w+', s, re.IGNORECASE)
    ) and not re.search(r'Contents', s, re.IGNORECASE))
    
    if len(chapter_headers) > 2:
        return 'headers'
    
    # Handle books with different chapter naming conventions (like "Mowgli's Brothers" in Jungle Book)
    headings_with_links = []
    for heading in soup.find_all(['h1', 'h2', 'h3']):
        if heading.find('a', class_='pginternal') or heading.get('id'):
            headings_with_links.append(heading)
    
    if len(headings_with_links) > 2:
        return 'headings_with_ids'
    
    return 'unknown'


def extract_chapters_from_html(html_file: str) -> Dict[str, Any]:
    """
    Extract chapters from a Gutenberg HTML file.
    
    Args:
        html_file: Path to the HTML file
        
    Returns:
        Dictionary containing book data including chapters
    """
    with open(html_file, 'r', encoding='utf-8', errors='replace') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract title and author
    title, author = extract_title_author(soup)
    logger.info(f"Book: '{title}' by {author}")
    
    # Identify the chapter pattern
    pattern = identify_chapter_pattern(soup)
    logger.info(f"Identified chapter pattern: {pattern}")
    
    # Extract chapters based on the identified pattern
    chapters = []
    
    # Strategy 1: Extract chapters from table of contents
    if pattern == 'toc':
        contents_section = find_contents_section(soup)
        chapter_links = extract_chapter_links(contents_section)
        
        if chapter_links:
            for index, (chapter_id, chapter_number, chapter_title) in enumerate(chapter_links):
                # Determine next chapter ID for boundary detection
                next_chapter_id = None
                if index + 1 < len(chapter_links):
                    next_chapter_id = chapter_links[index + 1][0]
                
                # Extract chapter content
                chapter_text = extract_chapter_content(soup, chapter_id, next_chapter_id)
                
                # Format chapter number
                if not chapter_number:
                    display_number = index + 1
                else:
                    display_number = chapter_number
                
                # If no chapter title, try to extract from first line
                if not chapter_title and chapter_text:
                    first_line = chapter_text.split("\n")[0]
                    if len(first_line) < 100 and not first_line.startswith('[Image:'):
                        chapter_title = first_line
                        chapter_text = "\n\n".join(chapter_text.split("\n")[1:])
                
                # Add chapter to list
                chapters.append({
                    "number": display_number,
                    "title": chapter_title or f"Chapter {display_number}",
                    "text": chapter_text
                })
    
    # Strategy 2: Extract chapters from div.chapter elements
    elif pattern == 'divs':
        chapter_divs = soup.find_all('div', class_='chapter')
        
        for index, chapter_div in enumerate(chapter_divs):
            # Skip if this is the table of contents
            if is_introduction_or_preface(chapter_div.get_text()):
                continue
            
            # Extract chapter title
            chapter_heading = chapter_div.find(['h1', 'h2', 'h3', 'h4'])
            chapter_title = chapter_heading.get_text(strip=True) if chapter_heading else f"Chapter {index+1}"
            
            # Extract chapter number
            chapter_number = index + 1
            match = re.search(r'(?:CHAPTER|Chapter|STAVE)\s+([IVXLCDM\d]+)', chapter_title, re.IGNORECASE)
            if match:
                roman_or_num = match.group(1)
                try:
                    # Convert Roman numerals to integers if needed
                    if all(c in 'IVXLCDM' for c in roman_or_num.upper()):
                        chapter_number = roman_or_num
                    else:
                        chapter_number = int(roman_or_num)
                except ValueError:
                    chapter_number = index + 1
            
            # Extract chapter name (remove "CHAPTER X" part)
            chapter_name = chapter_title
            match = re.search(r'(?:CHAPTER|Chapter|STAVE)\s+[IVXLCDM\d]+\.?\s*(.+)?', chapter_title, re.IGNORECASE)
            if match and match.group(1):
                chapter_name = match.group(1).strip()
            
            # Extract all content from the div
            chapter_text = ""
            if chapter_div.get('id'):
                # If the div has an ID, use our chapter content extraction function
                chapter_text = extract_chapter_content(soup, chapter_div.get('id'), None)
            else:
                # Extract all paragraphs, images, and other content
                content_elements = []
                
                # Skip the heading and get all paragraphs
                skip_heading = True
                for elem in chapter_div.find_all(['p', 'pre', 'img', 'table']):
                    if skip_heading and elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        skip_heading = False
                        continue
                    
                    if elem.name == 'p':
                        content_elements.append(elem.get_text(strip=True))
                    elif elem.name == 'pre':
                        content_elements.append(elem.get_text(strip=True))
                    elif elem.name == 'img':
                        src = elem.get('src', '')
                        if src:
                            content_elements.append(f"[Image: {src}]")
                
                chapter_text = "\n\n".join([p for p in content_elements if p])
            
            # Add chapter to list
            chapters.append({
                "number": chapter_number,
                "title": chapter_name,
                "text": chapter_text
            })
    
    # Strategy 3: Extract chapters from headers
    elif pattern in ['headers', 'headings_with_ids']:
        # Find all potential chapter headers
        if pattern == 'headers':
            # Standard chapter headers
            chapter_headers = soup.find_all(['h1', 'h2', 'h3'], string=lambda s: s and (
                re.search(r'(?:CHAPTER|Chapter|STAVE)\s+[IVXLCDM\d]+', s, re.IGNORECASE) or
                re.search(r'^(?:CHAPTER|Chapter|STAVE)\s+\w+', s, re.IGNORECASE)
            ) and not re.search(r'Contents', s, re.IGNORECASE))
        else:
            # Headers with IDs or internal links
            chapter_headers = []
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                if (heading.get('id') or heading.find('a', class_='pginternal')) and not is_introduction_or_preface(heading.get_text()):
                    chapter_headers.append(heading)
        
        for index, header in enumerate(chapter_headers):
            # Skip introductory material
            if is_introduction_or_preface(header.get_text()):
                continue
            
            # Extract chapter title
            chapter_title = header.get_text(strip=True)
            
            # Try to extract chapter number
            chapter_number = index + 1
            match = re.search(r'(?:CHAPTER|Chapter|STAVE)\s+([IVXLCDM\d]+)', chapter_title, re.IGNORECASE)
            if match:
                roman_or_num = match.group(1)
                try:
                    # Convert Roman numerals to integers if needed
                    if all(c in 'IVXLCDM' for c in roman_or_num.upper()):
                        chapter_number = roman_or_num
                    else:
                        chapter_number = int(roman_or_num)
                except ValueError:
                    chapter_number = index + 1
            
            # Try to extract chapter name
            chapter_name = chapter_title
            match = re.search(r'(?:CHAPTER|Chapter|STAVE)\s+[IVXLCDM\d]+\.?\s*(.+)?', chapter_title, re.IGNORECASE)
            if match and match.group(1):
                chapter_name = match.group(1).strip()
            else:
                # For non-standard chapter titles, use the whole title
                # But remove leading/trailing decorations if present
                chapter_name = re.sub(r'^[^a-zA-Z0-9]*|[^a-zA-Z0-9]*$', '', chapter_title)
            
            # Determine chapter boundaries
            chapter_id = header.get('id', '')
            next_chapter_id = None
            
            # If header has an ID, use it for content extraction
            if chapter_id:
                if index + 1 < len(chapter_headers) and chapter_headers[index + 1].get('id'):
                    next_chapter_id = chapter_headers[index + 1].get('id')
                chapter_text = extract_chapter_content(soup, chapter_id, next_chapter_id)
            else:
                # If header doesn't have an ID, use sequential extraction
                next_header = None
                if index + 1 < len(chapter_headers):
                    next_header = chapter_headers[index + 1]
                
                # Collect all paragraphs until the next chapter header
                paragraphs = []
                current = header.find_next()
                
                while current and (not next_header or current != next_header):
                    if current.name == 'p':
                        paragraphs.append(current.get_text(strip=True))
                    elif current.name == 'img':
                        src = current.get('src', '')
                        if src:
                            paragraphs.append(f"[Image: {src}]")
                    elif current.name == 'pre':
                        paragraphs.append(current.get_text(strip=True))
                    
                    current = current.find_next()
                    if not current:
                        break
                
                # Join paragraphs with proper spacing
                chapter_text = "\n\n".join([p for p in paragraphs if p])
            
            # Add chapter to list
            chapters.append({
                "number": chapter_number,
                "title": chapter_name,
                "text": chapter_text
            })
    
    # Strategy 4: If all else fails, try to extract whole text as one chapter
    if not chapters:
        logger.warning("Could not find chapter structure, extracting whole text")
        
        # Try to find main content div
        main_content = soup.find('div', id=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))
        if not main_content:
            main_content = soup.body
        
        # Extract all paragraphs
        paragraphs = main_content.find_all('p')
        content_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        chapters.append({
            "number": 1,
            "title": title,
            "text": content_text
        })
    
    # Special handling for books where chapters don't have good titles
    for chapter in chapters:
        if not chapter["title"] or chapter["title"] == f"Chapter {chapter['number']}":
            # Try to extract title from first line of text
            lines = chapter["text"].split("\n")
            if lines and lines[0]:
                first_line = lines[0]
                if len(first_line) < 100 and not first_line.startswith('[Image:'):
                    chapter["title"] = first_line
                    chapter["text"] = "\n\n".join(lines[1:])
    
    # Final cleanup and filtering
    filtered_chapters = []
    for chapter in chapters:
        # Skip empty chapters
        if not chapter["text"].strip():
            continue
            
        # Skip chapters that are clearly not content chapters
        if is_introduction_or_preface(chapter["title"]) and len(chapters) > 3:
            continue
            
        filtered_chapters.append(chapter)
    
    logger.info(f"Successfully extracted {len(filtered_chapters)} chapters")
    
    return {
        "title": title,
        "author": author,
        "chapters": filtered_chapters
    }


def create_json_book(book_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert the extracted book data to the riverst JSON format.
    
    Args:
        book_data: Dictionary containing book data
        
    Returns:
        JSON structure for the book
    """
    pages = []
    
    for chapter in book_data["chapters"]:
        chapter_number = chapter['number']
        chapter_title = chapter['title']
        
        # Format the chapter header
        if isinstance(chapter_number, int):
            header = f"**Chapter {chapter_number}: {chapter_title}**"
        else:
            header = f"**{chapter_title}**"
        
        text = f"{header}\n\n{chapter['text']}"
        vocab_words = extract_vocab_words(chapter['text'], max_words=5)
        
        page = {
            "text": text,
            "image": "",
            "vocab_words": vocab_words
        }
        
        pages.append(page)
    
    json_output = {
        "reading_context": {
            "indexable_by": "pages",
            "current_index": None,
            "book_title": book_data["title"],
            "book_author": book_data["author"],
            "pages": pages
        }
    }
    
    return json_output


def find_image_folder(html_file: str) -> str:
    """
    Find the image folder associated with the HTML file.
    
    Args:
        html_file: Path to the HTML file
        
    Returns:
        Path to the image folder
    """
    # Check for 'images' folder in the same directory
    html_dir = os.path.dirname(os.path.abspath(html_file))
    images_dir = os.path.join(html_dir, 'images')
    
    if os.path.isdir(images_dir):
        return images_dir
    
    # If no images folder, check if images are in the same directory
    image_files = [f for f in os.listdir(html_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    if image_files:
        return html_dir
    
    # If no images found, return the HTML directory anyway
    return html_dir


@click.command()
@click.argument('html_file', type=click.Path(exists=True))
@click.option('--output-dir', type=click.Path(exists=True), help='Custom output directory (defaults to assets/books)')
@click.option('--force', is_flag=True, help='Overwrite existing output if it exists')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def main(html_file: str, output_dir: str = None, force: bool = False, debug: bool = False) -> None:
    """
    Convert a Gutenberg HTML book to the riverst JSON format.
    
    Args:
        html_file: Path to the HTML file
        output_dir: Custom output directory (defaults to assets/books)
        force: Overwrite existing output if it exists
        debug: Enable debug logging
    """
    # Set log level
    if debug:
        logger.setLevel(logging.DEBUG)
    
    # Get absolute path to assets/books directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if output_dir:
        output_dir = os.path.abspath(output_dir)
    else:
        output_dir = os.path.abspath(os.path.join(script_dir, "..", "..", "assets", "books"))
    
    try:        
        # Extract book data
        book_data = extract_chapters_from_html(html_file)
        
        # Display book info
        click.echo(f"Book Title: {book_data['title']}")
        click.echo(f"Author: {book_data['author']}")
        click.echo(f"Number of chapters detected: {len(book_data['chapters'])}")
        
        # Print chapter titles for verification
        for i, chapter in enumerate(book_data['chapters']):
            click.echo(f"  Chapter {i+1}: {chapter['title']} ({len(chapter['text'])} chars)")
        
        # Setup output directories
        book_dir = setup_output_directories(output_dir, book_data["title"])
        output_file = os.path.join(book_dir, "paginated_story.json")
        
        # Check if output already exists
        if os.path.exists(output_file) and not force:
            overwrite = click.confirm(
                f"Output file already exists at {output_file}. Overwrite?", 
                default=False
            )
            if not overwrite:
                click.echo("Conversion cancelled.")
                return
        
        # Create JSON structure
        json_output = create_json_book(book_data)
        
        # Copy any images to the book directory
        image_folder = find_image_folder(html_file)
        images_copied = 0
        
        for img_file in os.listdir(image_folder):
            if img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                img_path = os.path.join(image_folder, img_file)
                img_dest = os.path.join(book_dir, 'images', img_file)
                
                # Create images directory if it doesn't exist
                os.makedirs(os.path.join(book_dir, 'images'), exist_ok=True)
                
                # Copy the image
                import shutil
                shutil.copy2(img_path, img_dest)
                images_copied += 1
        
        click.echo(f"Copied {images_copied} images")
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, ensure_ascii=False, indent=2)
        
        # Success message
        click.echo(f"\nBook '{book_data['title']}' successfully processed")
        click.echo(f"Number of pages in JSON: {len(json_output['reading_context']['pages'])}")
        click.echo(f"Output saved to: {output_file}")
        
    except Exception as e:
        click.echo(f"Error: {e}")
        if debug:
            import traceback
            click.echo(traceback.format_exc())


if __name__ == "__main__":
    main()