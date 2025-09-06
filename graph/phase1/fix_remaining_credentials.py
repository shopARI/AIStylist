#!/usr/bin/env python3
"""
Fix Remaining Hardcoded Credentials
Targeted fix for the remaining hardcoded Qdrant API keys
"""

import os
import re
from pathlib import Path


def fix_remaining_credentials():
    """Fix remaining hardcoded credentials in all files"""
    working_dir = Path("/home/leo/AIStylist/graph/phase1")
    qdrant_api_key_pattern = r'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.eyJhY2Nlc3MiOiJtIn0\.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg'
    
    files_fixed = 0
    total_replacements = 0
    
    for py_file in working_dir.glob("**/*.py"):
        if py_file.name in ['fix_remaining_credentials.py', 'secure_refactor.py']:
            continue
            
        try:
            content = py_file.read_text()
            original_content = content
            
            # Replace any remaining hardcoded API key references
            replacements_made = 0
            
            # Pattern 1: Direct assignment
            pattern1 = f'self.qdrant_api_key = "{qdrant_api_key_pattern}"'
            if pattern1 in content:
                content = content.replace(pattern1, 'self.qdrant_api_key = self.db_config.qdrant_api_key')
                replacements_made += 1
            
            # Pattern 2: In QdrantClient constructor
            pattern2 = f'api_key="{qdrant_api_key_pattern}"'
            if pattern2 in content:
                content = content.replace(pattern2, 'api_key=self.db_config.qdrant_api_key')
                replacements_made += 1
            
            # Pattern 3: Direct string
            pattern3 = f'"{qdrant_api_key_pattern}"'
            if pattern3 in content:
                content = content.replace(pattern3, 'self.db_config.qdrant_api_key')
                replacements_made += 1
                
            # Pattern 4: Other variations
            content = re.sub(
                rf'["\']?{re.escape(qdrant_api_key_pattern)}["\']?',
                'self.db_config.qdrant_api_key',
                content
            )
            
            if content != original_content:
                # Count actual changes
                actual_changes = len(re.findall(qdrant_api_key_pattern, original_content)) - len(re.findall(qdrant_api_key_pattern, content))
                if actual_changes > 0:
                    py_file.write_text(content)
                    files_fixed += 1
                    total_replacements += actual_changes
                    print(f"✅ Fixed {py_file}: {actual_changes} replacements")
        
        except Exception as e:
            print(f"❌ Error fixing {py_file}: {e}")
    
    print(f"\n📊 Summary:")
    print(f"Files fixed: {files_fixed}")
    print(f"Total replacements: {total_replacements}")
    
    # Verify no credentials remain
    files_still_with_creds = []
    for py_file in working_dir.glob("**/*.py"):
        if py_file.name in ['fix_remaining_credentials.py', 'secure_refactor.py']:
            continue
            
        try:
            content = py_file.read_text()
            if re.search(qdrant_api_key_pattern, content):
                files_still_with_creds.append(str(py_file))
        except:
            pass
    
    if files_still_with_creds:
        print(f"⚠️ Files still with credentials: {len(files_still_with_creds)}")
        for file in files_still_with_creds:
            print(f"  • {file}")
        return False
    else:
        print("✅ All hardcoded credentials removed successfully!")
        return True


if __name__ == "__main__":
    success = fix_remaining_credentials()
    exit(0 if success else 1)