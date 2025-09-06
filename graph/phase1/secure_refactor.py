#!/usr/bin/env python3
"""
Secure Refactor Script
Replaces all hardcoded credentials with secure configuration management
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple


class SecureRefactor:
    """Refactors hardcoded credentials to use secure configuration"""
    
    def __init__(self):
        self.working_dir = Path("/home/leo/AIStylist/graph/phase1")
        self.sensitive_patterns = {
            'neo4j_password': r'6D%q@jbYmstkK2i3oW5z6B6outew9m93',
            'qdrant_api_key': r'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.eyJhY2Nlc3MiOiJtIn0\.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg',
            'openai_api_key': r'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'
        }
        
        self.replacements = {
            # Neo4j configuration
            'self.neo4j_url = "bolt://0.0.0.0:17687"': 'self.db_config = get_database_config()\n        self.neo4j_url = self.db_config.neo4j_url',
            'self.neo4j_user = "neo4j"': 'self.neo4j_user = self.db_config.neo4j_user',
            f'self.neo4j_password = "{self.sensitive_patterns["neo4j_password"]}"': 'self.neo4j_password = self.db_config.neo4j_password',
            
            # Qdrant configuration
            f'self.qdrant_url = "https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io"': 'self.qdrant_url = self.db_config.qdrant_url',
            f'self.qdrant_api_key = "{self.sensitive_patterns["qdrant_api_key"]}"': 'self.qdrant_api_key = self.db_config.qdrant_api_key',
            'self.collection_name = "fashion_products"': 'self.collection_name = self.db_config.collection_name',
            
            # OpenAI configuration  
            f'openai_api_key = "{self.sensitive_patterns["openai_api_key"]}"': 'ai_config = get_ai_config()\n        openai_api_key = ai_config.openai_api_key',
            f'self.openai_api_key = "{self.sensitive_patterns["openai_api_key"]}"': 'self.ai_config = get_ai_config()\n        self.openai_api_key = self.ai_config.openai_api_key',
        }
        
        self.import_statement = "from config import get_database_config, get_ai_config, get_system_config"
        
    def find_files_with_credentials(self) -> List[Path]:
        """Find all Python files containing hardcoded credentials"""
        files_with_creds = []
        
        for py_file in self.working_dir.glob("**/*.py"):
            if py_file.name in ['secure_refactor.py', 'config.py']:
                continue
                
            try:
                content = py_file.read_text()
                
                # Check for any sensitive patterns
                for pattern_name, pattern in self.sensitive_patterns.items():
                    if re.search(pattern, content):
                        files_with_creds.append(py_file)
                        break
                        
            except Exception as e:
                print(f"Warning: Could not read {py_file}: {e}")
        
        return files_with_creds
    
    def refactor_file(self, file_path: Path) -> Dict:
        """Refactor a single file to use secure configuration"""
        result = {
            'file': str(file_path),
            'success': False,
            'changes_made': 0,
            'errors': []
        }
        
        try:
            content = file_path.read_text()
            original_content = content
            
            # Add import statement at the top if not present
            if "from config import" not in content and any(pattern in content for pattern in self.sensitive_patterns.values()):
                # Find the right place to add import
                lines = content.split('\n')
                import_line_added = False
                
                for i, line in enumerate(lines):
                    if line.strip().startswith('import ') or line.strip().startswith('from '):
                        continue
                    elif line.strip() == '' or line.strip().startswith('#'):
                        continue
                    else:
                        # Insert import before the first non-import line
                        lines.insert(i, self.import_statement)
                        import_line_added = True
                        break
                
                if import_line_added:
                    content = '\n'.join(lines)
                    result['changes_made'] += 1
            
            # Apply all replacements
            for old_pattern, new_pattern in self.replacements.items():
                if old_pattern in content:
                    content = content.replace(old_pattern, new_pattern)
                    result['changes_made'] += 1
            
            # Replace any remaining raw credential strings
            for pattern_name, pattern in self.sensitive_patterns.items():
                # Only replace if it's a string literal (quoted)
                quoted_patterns = [f'"{pattern}"', f"'{pattern}'"]
                for quoted_pattern in quoted_patterns:
                    if quoted_pattern in content:
                        if pattern_name == 'neo4j_password':
                            content = content.replace(quoted_pattern, 'self.db_config.neo4j_password')
                        elif pattern_name == 'qdrant_api_key':
                            content = content.replace(quoted_pattern, 'self.db_config.qdrant_api_key')
                        elif pattern_name == 'openai_api_key':
                            content = content.replace(quoted_pattern, 'self.ai_config.openai_api_key')
                        result['changes_made'] += 1
            
            # Only write if changes were made
            if content != original_content:
                # Create backup
                backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
                backup_path.write_text(original_content)
                
                # Write refactored content
                file_path.write_text(content)
                result['success'] = True
                print(f"✅ Refactored: {file_path} ({result['changes_made']} changes)")
            else:
                result['success'] = True  # No changes needed
                
        except Exception as e:
            result['errors'].append(str(e))
            print(f"❌ Error refactoring {file_path}: {e}")
        
        return result
    
    def verify_no_credentials_remain(self) -> Dict:
        """Verify no hardcoded credentials remain in any files"""
        verification_result = {
            'files_checked': 0,
            'files_with_credentials': [],
            'clean': True
        }
        
        for py_file in self.working_dir.glob("**/*.py"):
            if py_file.name in ['secure_refactor.py', 'config.py']:
                continue
                
            try:
                content = py_file.read_text()
                verification_result['files_checked'] += 1
                
                # Check for any remaining sensitive patterns
                for pattern_name, pattern in self.sensitive_patterns.items():
                    if re.search(pattern, content):
                        verification_result['files_with_credentials'].append({
                            'file': str(py_file),
                            'credential_type': pattern_name
                        })
                        verification_result['clean'] = False
                        
            except Exception as e:
                print(f"Warning: Could not verify {py_file}: {e}")
        
        return verification_result
    
    def run_refactor(self) -> Dict:
        """Run complete secure refactor process"""
        print("🔒 Starting Secure Credential Refactor")
        print("=" * 50)
        
        # Find files with credentials
        files_with_creds = self.find_files_with_credentials()
        print(f"Found {len(files_with_creds)} files with hardcoded credentials")
        
        if not files_with_creds:
            print("✅ No files with hardcoded credentials found!")
            return {'status': 'clean', 'files_processed': 0}
        
        # Refactor each file
        refactor_results = []
        successful_refactors = 0
        
        for file_path in files_with_creds:
            result = self.refactor_file(file_path)
            refactor_results.append(result)
            
            if result['success']:
                successful_refactors += 1
        
        # Verify no credentials remain
        print(f"\n🔍 Verifying credential removal...")
        verification = self.verify_no_credentials_remain()
        
        # Generate summary
        summary = {
            'status': 'completed',
            'files_found_with_credentials': len(files_with_creds),
            'files_successfully_refactored': successful_refactors,
            'total_changes_made': sum(r['changes_made'] for r in refactor_results),
            'verification_clean': verification['clean'],
            'files_still_with_credentials': len(verification['files_with_credentials']),
            'refactor_results': refactor_results,
            'verification_result': verification
        }
        
        # Print summary
        print(f"\n📊 REFACTOR SUMMARY:")
        print(f"Files with credentials found: {summary['files_found_with_credentials']}")
        print(f"Files successfully refactored: {summary['files_successfully_refactored']}")
        print(f"Total changes made: {summary['total_changes_made']}")
        print(f"Verification clean: {'✅' if summary['verification_clean'] else '❌'}")
        
        if not summary['verification_clean']:
            print(f"⚠️ Files still containing credentials: {summary['files_still_with_credentials']}")
            for file_info in verification['files_with_credentials']:
                print(f"  • {file_info['file']}: {file_info['credential_type']}")
        
        return summary


def main():
    """Run secure refactor"""
    refactor = SecureRefactor()
    result = refactor.run_refactor()
    
    if result['verification_clean']:
        print("\n🎉 SECURE REFACTOR COMPLETED SUCCESSFULLY!")
        print("All hardcoded credentials have been removed.")
        print("\n📝 Next steps:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your actual credentials in .env")
        print("3. Ensure .env is in .gitignore (already added)")
        print("4. Test the configuration with: python config.py")
    else:
        print("\n❌ REFACTOR INCOMPLETE")
        print("Some files still contain hardcoded credentials.")
        print("Please review and fix manually before committing.")
        return False
    
    return True


if __name__ == "__main__":
    main()