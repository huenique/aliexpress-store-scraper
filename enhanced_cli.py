#!/usr/bin/env python3
"""Backward compatibility wrapper for enhanced_cli.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from aliexpress_store_scraper.cli.enhanced_cli import main

if __name__ == "__main__":
    main()
