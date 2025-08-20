#!/usr/bin/env python3
"""Backward compatibility wrapper for cli.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from aliexpress_store_scraper.cli.cli import main

if __name__ == "__main__":
    main()
