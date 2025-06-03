"""
This module provides functions to scrape book information from a given 
Project Gutenberg URL and convert it to the riverst book format.
"""

import re
import json
import requests
import click
import os
import logging
from typing import Dict, List, Tuple, Any, Optional
from collections import Counter

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

def extract_chapter_info(contents_text: str) -> List[Dict[str, Any]]:
    """
    Extract chapter information from table of contents text using dynamic patterns.
    
    Args:
        contents_text: The contents section text
        
    Returns:
        List of dictionaries containing chapter information
    """
    chapters = []
    
    # Dynamic pattern components
    number_patterns = {
        'roman': r'[IVXLC]+',
        'arabic': r'\d+',
        'word': r'(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)'
    }
    
    # Build dynamic patterns for different chapter formats
    patterns = []
    
    # Chapter/Part/Stave/etc with numbers
    for prefix in ['Chapter', 'Stave', 'Book', 'Part', 'Story']:
        for num_type, num_pattern in number_patterns.items():
            # "Chapter I. Title" or "Chapter I Title"
            patterns.append((
                rf'^{prefix}\s+({num_pattern})\.?\s*:?\s*(.+?)(?:\s*\.\s*\.\s*\d+)?$',
                prefix.lower(),
                num_type
            ))
    
    # Just numbers with titles
    for num_type, num_pattern in number_patterns.items():
        # "I. Title" or "1. Title"
        patterns.append((
            rf'^({num_pattern})\.?\s+(.+?)(?:\s*\.\s*\.\s*\d+)?$',
            'chapter',
            num_type
        ))
    
    # Special standalone titles (Introduction, Preface, etc.)
    patterns.append((
        r'^(Introduction|Preface|Prologue|Epilogue|Foreword|Dedication|Voyage|Tale)(?:\s*\.\s*\.\s*\d+)?$',
        'special',
        None
    ))
    
    # Custom patterns for specific titles (like "THE OLD SEA-DOG AT THE ADMIRAL BENBOW")
    patterns.append((
        r'^([A-Z][A-Z\s\-\']+)(?:\s*\.\s*\.\s*\.+)?$',  # All caps titles with optional dots
        'title',
        None
    ))
    
    # Process each line
    for line in contents_text.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Skip PART headers without specific content
        if re.match(r'^PART\s+[A-Z]+\s*$', line, re.IGNORECASE):
            continue
        
        # Try each pattern
        for pattern, chapter_type, num_type in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                if chapter_type == 'special':
                    chapters.append({
                        'type': chapter_type,
                        'number': None,
                        'title': match.group(1),
                        'full_text': line
                    })
                else:
                    chapters.append({
                        'type': chapter_type,
                        'number': match.group(1),
                        'title': match.group(2).strip() if match.lastindex > 1 else '',
                        'full_text': line
                    })
                break
        else:
            # If no pattern matched but line looks like a title
            # (starts with capital, not too short, not all caps unless it's short)
            if (len(line) > 3 and line[0].isupper() and 
                (not line.isupper() or len(line) < 20)):
                chapters.append({
                    'type': 'title',
                    'number': None,
                    'title': line,
                    'full_text': line
                })
    
    return chapters

def create_dynamic_pattern(chapter: Dict[str, Any]) -> List[str]:
    """
    Create flexible regex patterns for finding a chapter in the main text.
    
    Args:
        chapter: Dictionary containing chapter information
        
    Returns:
        List of regex pattern strings
    """
    patterns = []
    
    # Escape and prepare title
    title = re.escape(chapter['title']) if chapter['title'] else ''
    # Allow for different apostrophe types
    title = title.replace(r"\'", r"['\u2019\u0027]")
    
    # For all caps titles, also create a variant with normal capitalization
    normal_case_title = None
    if chapter['title'] and chapter['title'].isupper() and len(chapter['title']) > 3:
        normal_case_title = re.escape(chapter['title'].title())  # First letter of each word capitalized
        normal_case_title = normal_case_title.replace(r"\'", r"['\u2019\u0027]")
    
    if chapter['number']:
        number = chapter['number']
        chapter_type = chapter['type'].upper()
        
        # Handle Roman/Arabic numeral conversion for better matching
        alt_number = None
        if re.match(r'^[IVXLC]+$', number, re.IGNORECASE):  # If Roman numeral
            try:
                # Convert Roman to Arabic
                roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
                arabic = 0
                prev_value = 0
                for char in number.upper():
                    value = roman_map[char]
                    if value > prev_value:
                        arabic -= prev_value
                    else:
                        arabic += prev_value
                    prev_value = value
                arabic += prev_value
                alt_number = str(arabic)
            except (KeyError, ValueError):
                alt_number = None
        elif number.isdigit():  # If Arabic numeral
            # Convert Arabic to Roman (simplified for 1-20)
            roman_numerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                             'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX']
            try:
                arabic = int(number)
                if 1 <= arabic <= 20:
                    alt_number = roman_numerals[arabic-1]
            except ValueError:
                alt_number = None
        
        # Multiple spacing and case variations
        spacing_options = [r'\s+', r'\s*\n\s*', r'\s*:\s*', r'\s*\.\s*', r'\s*-\s*']
        
        # Create patterns with original number
        for spacing in spacing_options:
            # Type + Number + Title variations
            if title:
                patterns.extend([
                    rf"{chapter_type}{spacing}{number}{spacing}{title}",
                    rf"{chapter_type.lower()}{spacing}{number}{spacing}{title}",
                    rf"{chapter_type.title()}{spacing}{number}{spacing}{title}",
                ])
                
                # Add patterns with normal case title if available (for Treasure Island issue)
                if normal_case_title:
                    patterns.extend([
                        rf"{chapter_type}{spacing}{number}{spacing}{normal_case_title}",
                        rf"{chapter_type.lower()}{spacing}{number}{spacing}{normal_case_title}",
                        rf"{chapter_type.title()}{spacing}{number}{spacing}{normal_case_title}",
                    ])
            
            # Just number + title (common in actual text)
            if title and chapter['type'] in ['chapter', 'part']:
                patterns.append(rf"^{number}{spacing}{title}")
                if normal_case_title:
                    patterns.append(rf"^{number}{spacing}{normal_case_title}")
        
        # Add patterns with alternative number representation if available
        if alt_number:
            for spacing in spacing_options:
                if title:
                    patterns.extend([
                        rf"{chapter_type}{spacing}{alt_number}{spacing}{title}",
                        rf"{chapter_type.lower()}{spacing}{alt_number}{spacing}{title}",
                        rf"{chapter_type.title()}{spacing}{alt_number}{spacing}{title}",
                    ])
                    
                    # Add patterns with normal case title if available (for Treasure Island issue)
                    if normal_case_title:
                        patterns.extend([
                            rf"{chapter_type}{spacing}{alt_number}{spacing}{normal_case_title}",
                            rf"{chapter_type.lower()}{spacing}{alt_number}{spacing}{normal_case_title}",
                            rf"{chapter_type.title()}{spacing}{alt_number}{spacing}{normal_case_title}",
                        ])
                
                if title and chapter['type'] in ['chapter', 'part']:
                    patterns.append(rf"^{alt_number}{spacing}{title}")
                    if normal_case_title:
                        patterns.append(rf"^{alt_number}{spacing}{normal_case_title}")
        
        # Number alone at line start (for cases where title is on next line)
        patterns.append(rf"^{number}\s*$")
        if alt_number:
            patterns.append(rf"^{alt_number}\s*$")
        
    elif chapter['type'] == 'special' or chapter['type'] == 'title':
        # For special sections or standalone titles
        patterns.extend([
            rf"^{title}$",
            rf"\n{title}\n",
            rf"^{title}\s*\n"
        ])
        
        # Add patterns with normal case title if available
        if normal_case_title:
            patterns.extend([
                rf"^{normal_case_title}$",
                rf"\n{normal_case_title}\n",
                rf"^{normal_case_title}\s*\n"
            ])
            
        # For Arabian Nights-style tales with "THE TALKING BIRD" format
        if chapter['title'] and chapter['title'].isupper() and 'THE' in chapter['title']:
            # Try to match the title without "THE" prefix, as it might appear differently in the text
            simplified_title = re.escape(chapter['title'].replace('THE ', '').title())
            simplified_title = simplified_title.replace(r"\'", r"['\u2019\u0027]")
            patterns.extend([
                rf"^{simplified_title}$",
                rf"\n{simplified_title}\n", 
                rf"^{simplified_title}\s*\n",
                rf"^The\s+{simplified_title}$",
                rf"\nThe\s+{simplified_title}\n",
                rf"^The\s+{simplified_title}\s*\n"
            ])
    
    return patterns

def find_chapters_in_text(text: str, chapters: List[Dict[str, Any]]) -> List[Tuple[int, int, Dict[str, Any]]]:
    """
    Find chapter positions in the main text using dynamic patterns.
    
    Args:
        text: The main book text
        chapters: List of chapter information from TOC
        
    Returns:
        List of tuples (start_pos, end_pos, chapter_info)
    """
    # Special handling for books with pre-calculated positions (Christmas Carol, Arabian Nights)
    if chapters and (chapters[0].get('type') in ['stave', 'tale']) and 'position' in chapters[0]:
        stave_positions = [(ch['position'], ch) for ch in chapters]
        stave_positions.sort()  # Sort by position
        
        # Create final chapter list with proper boundaries
        final_chapters = []
        for i, (pos, chapter) in enumerate(stave_positions):
            # Store the heading match position
            chapter_info = chapter.copy()  # Create a copy to avoid modifying the original
            chapter_info['heading_start'] = pos
            chapter_info['heading_end'] = pos + len(chapter['full_text'])
            
            # The actual content starts after the heading
            content_start = chapter_info['heading_end']
            
            # End at the start of the next stave or end of text
            content_end = stave_positions[i+1][0] if i < len(stave_positions) - 1 else len(text)
            
            final_chapters.append((content_start, content_end, chapter_info))
        
        return final_chapters
    
    if not chapters:
        return [(0, len(text), {'type': 'full', 'title': 'Full Text'})]
    
    found_chapters = []
    
    # Create patterns for all chapters
    all_patterns = []
    chapter_pattern_map = {}
    
    for i, chapter in enumerate(chapters):
        patterns = create_dynamic_pattern(chapter)
        for pattern in patterns:
            all_patterns.append(f'({pattern})')
            chapter_pattern_map[len(all_patterns) - 1] = i
    
    # Compile combined pattern
    combined_pattern = '|'.join(all_patterns)
    try:
        regex = re.compile(combined_pattern, re.MULTILINE | re.IGNORECASE)
    except re.error:
        # If pattern is too complex, fall back to simpler approach
        return fallback_chapter_search(text, chapters)
    
    # Find all matches
    matches = list(regex.finditer(text))
    
    if not matches:
        # Try fallback if no matches found
        return fallback_chapter_search(text, chapters)
    
    # Map matches to chapters
    for match in matches:
        # Find which group matched
        for group_idx in range(len(match.groups())):
            if match.group(group_idx + 1):
                if group_idx in chapter_pattern_map:
                    chapter_idx = chapter_pattern_map[group_idx]
                    
                    # Check for already existing match nearby to avoid duplicates (Treasure Island issue)
                    duplicate_found = False
                    for existing_start, _, _ in found_chapters:
                        # If there's already a match within 200 characters, consider this a duplicate
                        if abs(match.start() - existing_start) < 200:
                            duplicate_found = True
                            break
                    
                    if not duplicate_found:
                        found_chapters.append((match.start(), match.end(), chapters[chapter_idx]))
                break
    
    # Sort by position and remove duplicates
    found_chapters.sort(key=lambda x: x[0])
    
    # Special case for Peter Pan: detect the alternating chapter pattern
    # This happens when the TOC uses Roman numerals (I, II, III) but the text uses Arabic (1, 2, 3)
    if len(found_chapters) >= 10:
        # Check if we have a pattern of short distance between even-odd pairs
        distances = []
        for i in range(len(found_chapters) - 1):
            distances.append(found_chapters[i+1][0] - found_chapters[i][0])
        
        if len(distances) >= 4:
            # Check if we have alternating pattern of small and large distances
            alternating = True
            for i in range(0, len(distances) - 2, 2):
                if distances[i] > 1000 or distances[i+1] < 1000:
                    alternating = False
                    break
            
            if alternating:
                # We likely have duplicate chapter matches, keep only the correct ones
                filtered_chapters = []
                for i in range(0, len(found_chapters), 2):
                    if i < len(found_chapters):
                        filtered_chapters.append(found_chapters[i])
                found_chapters = filtered_chapters
    
    # Create final chapter list with proper boundaries
    final_chapters = []
    for i, (start, end, chapter) in enumerate(found_chapters):
        # Store the heading match position for title formatting later
        chapter = chapter.copy()  # Create a copy to avoid modifying the original
        chapter['heading_start'] = start
        chapter['heading_end'] = end
        
        # The actual content starts after the heading
        content_start = end
        
        # End at the start of the next chapter or end of text
        content_end = found_chapters[i+1][0] if i < len(found_chapters) - 1 else len(text)
        
        # Make sure we have enough content
        if content_end - content_start < 20 and i < len(found_chapters) - 1:
            # This chapter is too short, probably a false match - try to find the next boundary
            for j in range(i+1, min(i+3, len(found_chapters))):
                if found_chapters[j][0] - content_start > 1000:
                    content_end = found_chapters[j][0]
                    break
        
        final_chapters.append((content_start, content_end, chapter))
    
    return final_chapters

def fallback_chapter_search(text: str, chapters: List[Dict[str, Any]]) -> List[Tuple[int, int, Dict[str, Any]]]:
    """
    Simplified fallback method for finding chapters when complex patterns fail.
    
    Args:
        text: The main book text
        chapters: List of chapter information
        
    Returns:
        List of tuples (start_pos, end_pos, chapter_info)
    """
    # Try simpler patterns
    simple_patterns = [
        r'Chapter\s+[IVXLC\d]+',
        r'CHAPTER\s+[IVXLC\d]+',
        r'Stave\s+[IVXLC\d]+',  # For Christmas Carol
        r'STAVE\s+[IVXLC\d]+',
        r'\n[IVXLC]+\.\s',
        r'\n\d+\.\s',
        r'\nPart\s+[A-Z]+',
        r'\nPART\s+[A-Z]+',
        r'\nSTORY\s+[A-Z\d]+',  # For Arabian Nights
        r'\nTHE\s+[A-Z\s\-\']+' # For Tales with THE prefix
    ]
    
    all_matches = []
    for pattern in simple_patterns:
        matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
        all_matches.extend([(m.start(), m.end(), None) for m in matches])
    
    if len(all_matches) >= len(chapters) * 0.5:  # If we find at least half
        all_matches.sort(key=lambda x: x[0])
        
        # Create chapters from matches
        final_chapters = []
        for i, (start, end, _) in enumerate(all_matches):
            chapter_info = {'type': 'chapter', 'title': f'Chapter {i+1}', 'heading_start': start, 'heading_end': end}
            
            # The actual content starts after the heading
            content_start = end
            
            # End at the start of the next chapter or end of text
            content_end = all_matches[i+1][0] if i < len(all_matches) - 1 else len(text)
            
            final_chapters.append((content_start, content_end, chapter_info))
        
        return final_chapters
    
    # Last resort: return entire text
    return [(0, len(text), {'type': 'full', 'title': 'Full Text'})]

def parse_gutenberg_url(url: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse a Project Gutenberg URL and extract book information.
    
    Args:
        url: URL to a Project Gutenberg book
        
    Returns:
        Tuple containing book data in JSON format and the book title
    """
    response = requests.get(url)
    
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch the book from {url}. Status code: {response.status_code}")
    
    text = response.text
    
    # Normalize chapter numbering if there's a mismatch between Roman and Arabic numerals
    # This helps with books like Peter Pan where TOC uses Roman but text uses Arabic or vice versa
    
    # Define conversion dictionaries
    roman_to_arabic = {
        'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5',
        'VI': '6', 'VII': '7', 'VIII': '8', 'IX': '9', 'X': '10',
        'XI': '11', 'XII': '12', 'XIII': '13', 'XIV': '14', 'XV': '15',
        'XVI': '16', 'XVII': '17', 'XVIII': '18', 'XIX': '19', 'XX': '20'
    }
    
    arabic_to_roman = {v: k for k, v in roman_to_arabic.items()}
    
    # Check for chapter format in text
    roman_chapters = len(re.findall(r'Chapter\s+[IVX]+', text, re.IGNORECASE))
    arabic_chapters = len(re.findall(r'Chapter\s+\d+', text, re.IGNORECASE))
    
    # If both formats exist, normalize to the more common one
    if roman_chapters > 0 and arabic_chapters > 0:
        if roman_chapters > arabic_chapters:
            # Convert Arabic to Roman
            for arabic, roman in arabic_to_roman.items():
                text = re.sub(r'(Chapter\s+)' + arabic + r'\b', r'\1' + roman, text, flags=re.IGNORECASE)
        else:
            # Convert Roman to Arabic
            for roman, arabic in roman_to_arabic.items():
                text = re.sub(r'(Chapter\s+)' + roman + r'\b', r'\1' + arabic, text, flags=re.IGNORECASE)
    
    # Extract title and author with better error handling
    title_match = re.search(r'Title:\s*(.+?)(?:\r?\n|$)', text)
    author_match = re.search(r'Author:\s*(.+?)(?:\r?\n|$)', text)
    
    # If standard metadata not found, try alternative patterns
    if not title_match:
        # Look for title in ALL CAPS after the start marker or at beginning
        title_match = re.search(r'(?:\*\*\* START.*?\r?\n+)?([A-Z][A-Z\s]+)', text, re.DOTALL)
        
    # Special case for A Christmas Carol - detect the structure
    christmas_carol_match = re.search(r'STAVE', text, re.IGNORECASE)
    is_christmas_carol = christmas_carol_match and ('Christmas Carol' in title_match.group(1) if title_match else False)
    
    title = title_match.group(1).strip() if title_match else "Unknown Title"
    author = author_match.group(1).strip() if author_match else "Unknown Author"
    
    # Clean up author (remove illustrator info if present)
    if author and "illustrator" in author.lower():
        author = re.sub(r'\s*\bIllustrator:.*', '', author)
    
    # Trim to main body using Gutenberg markers
    start_patterns = [
        r'\*\*\* START OF THE PROJECT GUTENBERG EBOOK [^\n]+\n',
        r'\*\*\* START OF THIS PROJECT GUTENBERG EBOOK [^\n]+\n',
        r'START OF THE PROJECT GUTENBERG EBOOK[^\n]+\n'
    ]
    
    for pattern in start_patterns:
        start_match = re.search(pattern, text, re.IGNORECASE)
        if start_match:
            text = text[start_match.end():]
            break
    
    end_patterns = [
        r'\*\*\* END OF THE PROJECT GUTENBERG EBOOK',
        r'\*\*\* END OF THIS PROJECT GUTENBERG EBOOK',
        r'END OF THE PROJECT GUTENBERG EBOOK'
    ]
    
    for pattern in end_patterns:
        end_match = re.search(pattern, text, re.IGNORECASE)
        if end_match:
            text = text[:end_match.start()]
            break
    
    # Extract contents section with more flexible patterns
    contents_patterns = [
        r'CONTENTS\s*\n(.*?)(?=\n\s*\n\s*\n)',
        r'Contents\s*\n(.*?)(?=\n\s*\n\s*\n)',
        r'TABLE OF CONTENTS\s*\n(.*?)(?=\n\s*\n\s*\n)',
        r'Table of Contents\s*\n(.*?)(?=\n\s*\n\s*\n)'
    ]
    
    contents_text = None
    for pattern in contents_patterns:
        contents_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if contents_match:
            contents_text = contents_match.group(1)
            text = text[contents_match.end():]
            break
    
    # Check for Arabian Nights type title format
    is_arabian_nights = 'Arabian Nights' in title_match.group(1) if title_match else False
    
    # Special case for A Christmas Carol or Arabian Nights
    chapters = []
    if is_christmas_carol:
        # Look for the staves directly in the text
        stave_matches = re.finditer(r'STAVE\s+([IVX]+)[.\s]*', text, re.IGNORECASE)
        stave_positions = []
        
        for match in stave_matches:
            stave_num = match.group(1)
            # Convert Roman numeral to number
            roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5}
            try:
                stave_number = roman_map.get(stave_num.upper(), 0)
                if stave_number > 0:
                    stave_positions.append((match.start(), stave_number))
            except (KeyError, ValueError):
                pass
        
        # Sort staves by position in text
        stave_positions.sort()
        
        # Create chapters list
        for i, (pos, number) in enumerate(stave_positions):
            chapters.append({
                'type': 'stave',
                'number': str(number),
                'title': f'Stave {number}',
                'full_text': f'Stave {number}',
                'position': pos
            })
            
    # If not Christmas Carol or no staves found, use regular method
    elif is_arabian_nights:
        # For Arabian Nights, look for tale/story titles
        tale_patterns = [
            r'\n([A-Z][A-Z\s\-\']+\s+OF\s+[A-Z][A-Z\s\-\']+)',  # THE TALE OF THE FISHERMAN
            r'\n(THE\s+[A-Z][A-Z\s\-\']+\s+BIRD)',              # THE TALKING BIRD
            r'\n(STORY\s+OF\s+[A-Z][A-Z\s\-\']+)',              # STORY OF THE FISHERMAN
            r'\n(SECOND\s+VOYAGE\s+OF\s+[A-Z][A-Z\s\-\']+)',    # SECOND VOYAGE OF SINBAD
        ]
        
        tale_positions = []
        for pattern in tale_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                tale_title = match.group(1).strip()
                tale_positions.append((match.start(), tale_title))
        
        # Sort by position in text
        tale_positions.sort()
        
        # Create chapters for each tale
        for i, (pos, title) in enumerate(tale_positions):
            chapters.append({
                'type': 'tale',
                'number': str(i+1),
                'title': title,
                'full_text': title,
                'position': pos
            })
            
    elif contents_text:
        chapters = extract_chapter_info(contents_text)
    
    # Find chapters in main text
    chapter_positions = find_chapters_in_text(text, chapters)
    
    # Create pages from chapters
    pages = []
    for start_pos, end_pos, chapter_info in chapter_positions:
        chapter_text = text[start_pos:end_pos]
        
        # Clean up whitespace characters for LLM consumption
        cleaned_text = re.sub(r'\r\n|\r|\n', ' ', chapter_text)  # Replace line breaks with spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Normalize multiple spaces to single space
        cleaned_text = cleaned_text.strip()  # Remove leading/trailing whitespace
        
        # Format chapter title if available
        if chapter_info.get('title'):
            # Since we've adjusted content boundaries to start after the heading,
            # we can simply prepend the formatted title to the cleaned text
            cleaned_text = f"**{chapter_info['title']}**\n\n{cleaned_text}"
        
        pages.append({
            "text": cleaned_text,
            "image": "",
            "vocab_words": extract_vocab_words(chapter_text)
        })
    
    # Filter out empty chapters
    non_empty_pages = []
    
    for page in pages:
        # Get the content after the title
        text = page["text"]
        title_end = text.find("\n\n")
        
        if title_end != -1:
            content = text[title_end+2:].strip()
            # Keep pages with actual content (more than 100 chars)
            if len(content) > 100:
                non_empty_pages.append(page)
        else:
            # If no title format found, keep the page if it has content
            if len(text.strip()) > 100:
                non_empty_pages.append(page)
    
    # If filtering removed all pages, keep all original pages
    if not non_empty_pages and pages:
        non_empty_pages = pages
    
    # Fix chapter titles if they appear to be incorrectly numbered (like in Peter Pan)
    # This addresses the case where we have Chapter 2, 4, 6, etc. instead of 1, 2, 3
    if len(non_empty_pages) > 5:
        title_pattern = r'\*\*Chapter (\d+)\*\*'
        chapter_numbers = []
        
        for page in non_empty_pages:
            match = re.match(title_pattern, page["text"])
            if match:
                chapter_numbers.append(int(match.group(1)))
        
        # Check if we have a pattern of even numbers only
        if chapter_numbers and all(num % 2 == 0 for num in chapter_numbers):
            # Renumber chapters correctly
            for i, page in enumerate(non_empty_pages):
                match = re.match(title_pattern, page["text"])
                if match:
                    # Replace the chapter number with the correct sequence (1, 2, 3...)
                    correct_number = i + 1
                    page["text"] = re.sub(title_pattern, f'**Chapter {correct_number}**', page["text"])
    
    # Create the final JSON structure
    json_output = {
        "reading_context": {
            "indexable_by": "pages",
            "current_index": None,
            "book_title": title,
            "book_author": author,
            "pages": non_empty_pages
        }
    }
    
    return json_output, title

@click.command()
@click.argument('url')
def main(url: str) -> None:
    """
    Scrape book information from a Project Gutenberg URL
    and save it to a JSON file in the correct assets/books directory.
    """
    # Get absolute path to assets/books directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.abspath(os.path.join(script_dir, "..", "assets", "books"))
    
    try:
        click.echo(f"Fetching book from URL: {url}")
        book_data, title = parse_gutenberg_url(url)
        
        # Create directory name from title
        book_dir_name = title.lower().replace(" ", "_").replace(":", "_").replace(";", "_").replace("/", "_")
        book_dir = os.path.join(output_dir, book_dir_name)
        
        os.makedirs(book_dir, exist_ok=True)
        os.makedirs(os.path.join(book_dir, "audios"), exist_ok=True)
        
        output_file = os.path.join(book_dir, "paginated_story.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(book_data, f, ensure_ascii=False, indent=2)
            
        click.echo(f"Book '{title}' successfully processed")
        click.echo(f"Number of chapters: {len(book_data['reading_context']['pages'])}")
        
    except Exception as e:
        click.echo(f"Error: {e}")

if __name__ == "__main__":
    main()