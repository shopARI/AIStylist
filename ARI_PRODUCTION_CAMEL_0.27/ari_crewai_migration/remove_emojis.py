#!/usr/bin/env python3
"""Remove all emojis from code and documentation"""

import re
import glob

# Common emojis to remove
EMOJI_PATTERN = re.compile(
    r'[\U0001F300-\U0001F9FF]|'  # Misc Symbols and Pictographs
    r'[\U0001F600-\U0001F64F]|'  # Emoticons
    r'[\U0001F680-\U0001F6FF]|'  # Transport and Map Symbols
    r'[\U00002600-\U000027BF]|'  # Misc symbols
    r'[\U0001F900-\U0001F9FF]|'  # Supplemental Symbols and Pictographs
    r'[]'  # Specific common emojis
)

def remove_emojis_from_file(filepath):
    """Remove emojis from a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove emojis
        clean_content = EMOJI_PATTERN.sub('', content)

        # Only write if changed
        if clean_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(clean_content)
            print(f"Cleaned: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

# Process all Python files
py_files = glob.glob('./**/*.py', recursive=True)
md_files = glob.glob('./**/*.md', recursive=True)

print("Removing emojis from Python files...")
py_count = sum(remove_emojis_from_file(f) for f in py_files)

print("\nRemoving emojis from Markdown files...")
md_count = sum(remove_emojis_from_file(f) for f in md_files)

print(f"\nTotal files cleaned:")
print(f"  Python: {py_count}")
print(f"  Markdown: {md_count}")
