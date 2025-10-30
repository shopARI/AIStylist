#!/usr/bin/env python3
"""
Remove all emojis from Python and Markdown files in the codebase.
"""
import os
import re
from pathlib import Path

# Emoji regex pattern (covers most emoji ranges)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
    "\U00002600-\U000026FF"  # miscellaneous symbols
    "\U00002B50"              # star
    "]+",
    flags=re.UNICODE
)


def remove_emojis_from_file(filepath):
    """Remove emojis from a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if file has emojis
        if EMOJI_PATTERN.search(content):
            # Remove emojis
            cleaned = EMOJI_PATTERN.sub('', content)

            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned)

            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main():
    """Main function to remove emojis from all Python and Markdown files."""
    base_dir = Path('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration')

    # Extensions to process
    extensions = ['.py', '.md']

    # Directories to skip
    skip_dirs = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv'}

    files_processed = 0
    files_modified = 0

    print("Scanning for emojis in Python and Markdown files...")

    for ext in extensions:
        for filepath in base_dir.rglob(f'*{ext}'):
            # Skip if in excluded directory
            if any(skip in filepath.parts for skip in skip_dirs):
                continue

            files_processed += 1
            if remove_emojis_from_file(filepath):
                files_modified += 1
                print(f"  Cleaned: {filepath.relative_to(base_dir)}")

    print(f"\nDone!")
    print(f"Files processed: {files_processed}")
    print(f"Files modified: {files_modified}")


if __name__ == '__main__':
    main()
