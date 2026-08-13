"""
Legacy file — MongoDB collection init is now handled by mongo_store.init_collections()
called from photos/apps.py PhotosConfig.ready().
"""


def initialize_mongodb():
    """No-op — kept for backwards compatibility with the management command."""
    pass
