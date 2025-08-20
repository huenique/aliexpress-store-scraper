"""
AliExpress Store Scraper Package
================================

A comprehensive Python package for scraping AliExpress product and store data.

Modules:
- clients: HTTP clients for AliExpress API interactions
- processors: Data processing and business logic
- cli: Command-line interface tools
- utils: Utility functions and helpers

Usage:
    python -m aliexpress_store_scraper [command] [options]

Direct imports:
    from aliexpress_store_scraper.clients.aliexpress_client import AliExpressClient
    from aliexpress_store_scraper.clients.enhanced_aliexpress_client import EnhancedAliExpressClient
    from aliexpress_store_scraper.utils.logger import ScraperLogger
"""

__version__ = "0.1.0"
__author__ = "huenique"

# Make common classes easily importable
try:
    from .clients.aliexpress_client import AliExpressClient
    from .clients.enhanced_aliexpress_client import EnhancedAliExpressClient
    from .utils.cookie_generator import CookieGenerator
    from .utils.logger import ScraperLogger

    __all__ = [
        "AliExpressClient",
        "EnhancedAliExpressClient",
        "ScraperLogger",
        "CookieGenerator",
    ]
except ImportError:
    # Dependencies may not be installed yet
    pass
