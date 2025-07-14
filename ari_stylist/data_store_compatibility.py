"""
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
