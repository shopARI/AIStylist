"""
Method Compatibility Updater
Automatically updates recommender files to use HybridDataStore methods
"""

import os
import re
import shutil
from typing import List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("method_updater")


class MethodUpdater:
    """Updates method calls in recommender files for HybridDataStore compatibility"""
    
    def __init__(self):
        # Define method mappings
        self.method_mappings = [
            # Simple renames
            (r'\.get_product_details\(', '.get_product('),
            
            # get_product_by_filter -> search_products with filters
            (r'\.get_product_by_filter\((.*?)\)', self.convert_get_product_by_filter),
            
            # get_products_by_category -> search_products with category filter
            (r'\.get_products_by_category\((.*?)\)', self.convert_get_products_by_category),
            
            # get_products_by_tag -> search_products with tag filter
            (r'\.get_products_by_tag\((.*?)\)', self.convert_get_products_by_tag),
            
            # get_all_products -> search_products with high limit
            (r'\.get_all_products\(\)', '.search_products(limit=1000)'),
        ]
        
        # Files to update
        self.recommender_files = [
            'multi_cluster_recommender.py',
            'hybrid_visual_recommender.py',
            'rfm_apriori_recommender_async.py',
            'memory_rag_recommender.py',
            'ensemble_recommender.py'
        ]
    
    def convert_get_product_by_filter(self, match):
        """Convert get_product_by_filter to search_products"""
        args = match.group(1)
        
        # Parse arguments
        filters = {}
        limit = 10
        
        # Extract named arguments
        category_match = re.search(r'category\s*=\s*["\']?([^"\']+)["\']?', args)
        if category_match:
            filters['category'] = category_match.group(1)
        
        tag_match = re.search(r'tag\s*=\s*["\']?([^"\']+)["\']?', args)
        if tag_match:
            filters['tag'] = tag_match.group(1)
        
        limit_match = re.search(r'limit\s*=\s*(\d+)', args)
        if limit_match:
            limit = limit_match.group(1)
        
        # Build new call
        if filters:
            filters_str = str(filters).replace("'", '"')
            return f'.search_products(filters={filters_str}, limit={limit})'
        else:
            return f'.search_products(limit={limit})'
    
    def convert_get_products_by_category(self, match):
        """Convert get_products_by_category to search_products"""
        category = match.group(1).strip().strip('"\'')
        return f'.search_products(filters={{"category": "{category}"}}, limit=10)'
    
    def convert_get_products_by_tag(self, match):
        """Convert get_products_by_tag to search_products"""
        tag = match.group(1).strip().strip('"\'')
        return f'.search_products(filters={{"tag": "{tag}"}}, limit=10)'
    
    def update_file(self, filepath: str) -> Tuple[bool, List[str]]:
        """Update a single file"""
        if not os.path.exists(filepath):
            logger.warning(f"File not found: {filepath}")
            return False, [f"File not found: {filepath}"]
        
        # Backup original
        backup_path = f"{filepath}.backup"
        shutil.copy2(filepath, backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        changes = []
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Apply mappings
            for pattern, replacement in self.method_mappings:
                if callable(replacement):
                    # Use function for complex replacements
                    new_content = re.sub(pattern, replacement, content)
                else:
                    # Simple string replacement
                    new_content = re.sub(pattern, replacement, content)
                
                if new_content != content:
                    # Find what changed
                    old_calls = re.findall(pattern, content)
                    changes.extend([f"Updated: {call}" for call in old_calls])
                    content = new_content
            
            # Check if we need to add imports
            if 'search_products' in content and 'from typing import' not in content:
                content = "from typing import Dict, Any\n" + content
                changes.append("Added typing imports")
            
            # Write updated content
            if content != original_content:
                with open(filepath, 'w') as f:
                    f.write(content)
                logger.info(f"Updated {filepath} with {len(changes)} changes")
                return True, changes
            else:
                logger.info(f"No changes needed for {filepath}")
                return True, []
                
        except Exception as e:
            logger.error(f"Error updating {filepath}: {e}")
            # Restore backup
            shutil.copy2(backup_path, filepath)
            return False, [f"Error: {str(e)}"]
    
    def update_all_recommenders(self):
        """Update all recommender files"""
        logger.info("Starting method compatibility updates...")
        
        results = {}
        
        for filename in self.recommender_files:
            logger.info(f"\nProcessing {filename}...")
            success, changes = self.update_file(filename)
            results[filename] = {
                'success': success,
                'changes': changes
            }
        
        # Print summary
        logger.info("\n" + "="*50)
        logger.info("UPDATE SUMMARY")
        logger.info("="*50)
        
        total_changes = 0
        failed_files = []
        
        for filename, result in results.items():
            if result['success']:
                change_count = len(result['changes'])
                total_changes += change_count
                logger.info(f"✅ {filename}: {change_count} changes")
                for change in result['changes'][:3]:  # Show first 3 changes
                    logger.info(f"   - {change}")
                if len(result['changes']) > 3:
                    logger.info(f"   ... and {len(result['changes']) - 3} more")
            else:
                failed_files.append(filename)
                logger.error(f"❌ {filename}: FAILED")
                for error in result['changes']:
                    logger.error(f"   - {error}")
        
        logger.info(f"\nTotal changes: {total_changes}")
        
        if failed_files:
            logger.error(f"Failed files: {', '.join(failed_files)}")
            logger.info("\nRestore original files with: ")
            for f in failed_files:
                logger.info(f"  mv {f}.backup {f}")
        else:
            logger.info("\n✅ All files updated successfully!")
            logger.info("\nTo restore original files if needed:")
            for f in self.recommender_files:
                logger.info(f"  mv {f}.backup {f}")
    
    def create_compatibility_wrapper(self):
        """Create a compatibility wrapper for gradual migration"""
        wrapper_code = '''"""
Compatibility wrapper for HybridDataStore
Provides backward compatibility for recommenders during migration
"""

class DataStoreCompatibilityWrapper:
    """Wraps HybridDataStore to provide old method names"""
    
    def __init__(self, data_store):
        self.data_store = data_store
    
    # Old method -> New method mappings
    
    async def get_product_details(self, product_id):
        """Backward compatibility for get_product_details"""
        return await self.data_store.get_product(product_id)
    
    async def get_product_by_filter(self, category=None, tag=None, limit=10, **kwargs):
        """Backward compatibility for get_product_by_filter"""
        filters = {}
        if category:
            filters['category'] = category
        if tag:
            filters['tag'] = tag
        
        return await self.data_store.search_products(
            filters=filters,
            limit=limit
        )
    
    async def get_products_by_category(self, category, limit=10):
        """Backward compatibility for get_products_by_category"""
        return await self.data_store.search_products(
            filters={'category': category},
            limit=limit
        )
    
    async def get_products_by_tag(self, tag, limit=10):
        """Backward compatibility for get_products_by_tag"""
        return await self.data_store.search_products(
            filters={'tag': tag},
            limit=limit
        )
    
    async def get_all_products(self, limit=1000):
        """Backward compatibility for get_all_products"""
        return await self.data_store.search_products(limit=limit)
    
    # Pass through all other methods
    def __getattr__(self, name):
        return getattr(self.data_store, name)
'''
        
        with open('data_store_compatibility.py', 'w') as f:
            f.write(wrapper_code)
        
        logger.info("\n✅ Created data_store_compatibility.py wrapper")
        logger.info("You can use this wrapper during migration:")
        logger.info("  from data_store_compatibility import DataStoreCompatibilityWrapper")
        logger.info("  wrapped_store = DataStoreCompatibilityWrapper(data_store)")


def main():
    """Run the method updater"""
    updater = MethodUpdater()
    
    print("Method Compatibility Updater")
    print("="*50)
    print("\nThis will update recommender files to use HybridDataStore methods.")
    print("Original files will be backed up with .backup extension.")
    
    response = input("\nProceed with updates? (y/N): ")
    
    if response.lower() == 'y':
        updater.update_all_recommenders()
        
        print("\nCreate compatibility wrapper? (y/N): ")
        if input().lower() == 'y':
            updater.create_compatibility_wrapper()
    else:
        print("Updates cancelled")


if __name__ == "__main__":
    main()