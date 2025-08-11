
# AliExpress Product Scraper

This project provides a fully reverse-engineered AliExpress client that interacts directly with AliExpress's internal MTOP API to extract comprehensive product data. It includes a command-line interface (CLI) for convenient usage and can also be used as a Python library.

## Overview

This client implements AliExpress's signature algorithm and authentication, based on analysis of their JavaScript source code. It does not scrape HTML; instead, it communicates with the official internal API endpoints for reliable and accurate data extraction.

## Features

- Reverse engineered signature algorithm (MD5-based, as used by AliExpress)
- Complete product data extraction: title, price, ratings, store information, shipping, variants, images, and more
- Direct integration with AliExpress MTOP API endpoints
- Command-line interface (CLI) for easy access
- Multiple output formats: human-readable, JSON, verbose
- Flexible input: supports both product URLs and IDs
- Single-module, production-ready implementation

## Quick Start

### CLI Usage

```bash
# Basic usage
python cli.py "https://www.aliexpress.us/item/3256809096800275.html" "your_cookie_here"

# Using product ID
python cli.py --product-id 3256809096800275 --cookie "your_cookie_here"

# JSON output
python cli.py -p 3256809096800275 -c "cookie" --json

# Verbose details
python cli.py -u "URL" -c "cookie" --verbose
```

### Python Library Usage

```python
from aliexpress_client import AliExpressClient

client = AliExpressClient()
cookie = "_m_h5_tk=your_token_here_1234567890; _m_h5_tk_enc=encrypted_token; ..."

# Get product data
product_data = client.get_product("3256809096800275", cookie)

# Print formatted summary
client.print_product_summary(product_data)
```

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/huenique/aliexpress-scraper.git
   cd aliexpress-scraper
   ```

2. **Install dependencies**:

   ```bash
   pip install requests
   # Or, if using uv:
   uv sync
   ```

3. **Obtain a fresh cookie from AliExpress**:
   - Visit <https://www.aliexpress.us> in your browser
   - Open Developer Tools (F12) and go to the Network tab
   - Refresh the page or open a product
   - Copy the entire 'Cookie' header from any request

## Usage Examples

### CLI Examples

```bash
# Get help
python cli.py --help

# Basic product info
python cli.py "https://www.aliexpress.us/item/3256809096800275.html" "cookie"

# Detailed information
python cli.py --product-id 3256809096800275 --cookie "cookie" --verbose

# JSON for integration
python cli.py -p 3256809096800275 -c "cookie" --json > product.json
```

### Library Examples

```python
from aliexpress_client import AliExpressClient
import json

client = AliExpressClient()
cookie = "your_fresh_cookie_here"

# Get product data
result = client.get_product("3256809096800275", cookie)

if result['success']:
   print(f"Product: {result['title']}")
   print(f"Price: {result['price']['sale_price']}")
   print(f"Rating: {result['rating']['score']} stars")
   # Save to JSON
   with open('product.json', 'w') as f:
      json.dump(result, f, indent=2)
else:
   print(f"Error: {result['error']}")
```

## Extracted Data

The scraper extracts the following product information:

- Basic Info: Title, product ID, description
- Pricing: Sale price, original price, currency, discounts
- Ratings: Star rating, total sales, customer reviews
- Store Details: Store name, seller rating, location, history
- Shipping: Delivery times, costs, carrier, shipping origin
- Variants: Colors, sizes, configurations, SKU options
- Media: Product images, gallery photos
- Metadata: API trace IDs, data sections, timestamps

```bash
usage: cli.py [-h] [-u PRODUCT_URL] [-p PRODUCT_ID] [-c COOKIE_STRING]
              [--json] [--pretty-json] [-v] [--raw] [url] [cookie]

Options:
  -h, --help            Show help message
  -u, --url             Product URL or ID
  -p, --product-id      Direct product ID
  -c, --cookie          Cookie string from browser
  --json               Output in JSON format
  --pretty-json        Pretty-printed JSON format
  -v, --verbose        Show detailed information
  --raw                Output raw API response
```

## Project Structure

```bash
aliexpress-scraper/
├── aliexpress_client.py    # Core scraper library
├── cli.py                  # Command-line interface
├── example.py              # Usage examples
├── CLI_README.md           # Detailed CLI documentation
├── cli_demo.sh             # CLI demonstration script
└── README.md               # This file
```

## Technical Details

- **Signature Algorithm**: `MD5(token + '&' + timestamp + '&' + appKey + '&' + data)`
- **API Protocol**: MTOP JSONP with callback wrapping
- **Authentication**: Cookie-based with `_m_h5_tk` tokens
- **Endpoints**: `acs.aliexpress.us/h5/mtop.aliexpress.pdp.pc.query/`
- **Response Format**: JSONP-wrapped JSON data

## Project Highlights

- Fully reverse engineered from AliExpress JavaScript source code
- Real API integration (not HTML scraping)
- Working signature algorithm
- Complete product data extraction and parsing
- CLI tool for command-line usage
- Production ready with error handling

## Documentation

- [CLI Documentation](CLI_README.md): Comprehensive CLI usage guide
- [Example Usage](example.py): Python usage examples
- [Demo Script](cli_demo.sh): CLI demonstration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with fresh cookies
5. Submit a pull request

## Important Notes

- Fresh cookies are required: AliExpress tokens expire regularly
- Rate limiting: Please be respectful to AliExpress servers
- Legal compliance: Use responsibly and respect AliExpress terms of service
- Educational purpose: This project is for learning and research purposes only
