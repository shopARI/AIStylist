#!/usr/bin/env python3
"""
Complete Emoji Removal Script
Removes ALL emojis from Python and Markdown files
"""

import os
import re
from pathlib import Path

# Comprehensive emoji pattern covering all common emojis
EMOJI_PATTERNS = [
    r'', r'', r'', r'', r'', r'', r'', r'',
    r'', r'', r'', r'', r'', r'', r'', r'',
    r'', r'', r'', r'', r'', r'', r'', r'',
    r'', r'', r'', r'', r'', r'', r'', r'',
    r'', r'', r'', r'', r'', r'', r'', r''
]

# Unicode ranges for emojis
UNICODE_EMOJI_PATTERN = re.compile(
    r'[\U0001F300-\U0001F9FF]|'  # Misc Symbols and Pictographs
    r'[\U0001F600-\U0001F64F]|'  # Emoticons
    r'[\U0001F680-\U0001F6FF]|'  # Transport and Map Symbols
    r'[\U00002600-\U000027BF]|'  # Misc symbols
    r'[\U0001F900-\U0001F9FF]|'  # Supplemental Symbols and Pictographs
    r'[\U00002700-\U000027BF]|'  # Dingbats
    r'[\U0001F1E0-\U0001F1FF]'   # Flags
)

def remove_emojis_from_text(text):
    """Remove all emojis from text"""
    # First remove specific emoji patterns
    for emoji in EMOJI_PATTERNS:
        text = text.replace(emoji, '')

    # Then remove unicode emojis
    text = UNICODE_EMOJI_PATTERN.sub('', text)

    return text

def process_file(filepath):
    """Remove emojis from a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        cleaned_content = remove_emojis_from_text(content)

        if original_content != cleaned_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Process all Python and Markdown files"""
    root_dir = Path('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration')

    files_to_process = []
    files_to_process.extend(root_dir.glob('**/*.py'))
    files_to_process.extend(root_dir.glob('**/*.md'))

    modified_count = 0
    total_count = 0

    print("=" * 80)
    print("REMOVING ALL EMOJIS FROM CODEBASE")
    print("=" * 80)

    for filepath in sorted(files_to_process):
        # Skip __pycache__ and .backup files
        if '__pycache__' in str(filepath) or '.backup' in str(filepath):
            continue

        total_count += 1
        if process_file(filepath):
            modified_count += 1
            print(f"Cleaned: {filepath.relative_to(root_dir)}")

    print("=" * 80)
    print(f"COMPLETE: Modified {modified_count}/{total_count} files")
    print("=" * 80)

if __name__ == '__main__':
    main()
