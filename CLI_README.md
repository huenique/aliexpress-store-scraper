# AliExpress CLI Scraper

A command-line tool to scrape AliExpress product data using reverse-engineered MTOP API calls.

## Features

✅ **Extract Complete Product Data**

- Product title, price, and ratings
- Store information and seller details
- Shipping costs and delivery times
- Available variants and options
- Product images

✅ **Flexible Input Options**

- Full product URLs
- Product IDs only
- Multiple URL formats supported

✅ **Multiple Output Formats**

- Human-readable text (default)
- JSON format for programmatic use
- Verbose mode with detailed information

✅ **Easy to Use**

- Simple command-line interface
- Clear error messages
- Built-in help

## Installation

```bash
# Install dependencies (if using pip)
pip install requests

# Or if using the project's virtual environment
cd /path/to/aliexpress-scraper
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

## Usage

### Basic Usage (Positional Arguments)

```bash
python cli.py "https://www.aliexpress.us/item/3256809096800275.html" "your_cookie_string"
```

### Named Arguments

```bash
# Using named arguments
python cli.py --url "https://www.aliexpress.us/item/3256809096800275.html" --cookie "your_cookie"

# Using product ID directly
python cli.py --product-id 3256809096800275 --cookie "your_cookie"

# Short flags
python cli.py -u "https://aliexpress.com/item/123.html" -c "cookie_string"
```

### Output Options

```bash
# Default human-readable output
python cli.py URL COOKIE

# Verbose output with detailed information
python cli.py URL COOKIE --verbose

# JSON output
python cli.py URL COOKIE --json

# Raw API response (for debugging)
python cli.py URL COOKIE --raw
```

### Supported URL Formats

The CLI supports various AliExpress URL formats:

```bash
https://www.aliexpress.us/item/3256809096800275.html
https://www.aliexpress.com/item/3256809096800275.html
https://aliexpress.us/item/3256809096800275.html
aliexpress.com/item/3256809096800275.html
3256809096800275  (direct product ID)
```

## Getting a Cookie

You need a fresh cookie from AliExpress for the scraper to work:

1. **Go to <www.aliexpress.us>** in your browser
2. **Open Developer Tools** (F12)
3. **Go to Network tab**
4. **Refresh the page** or browse a product
5. **Find any request** and look for the `Cookie` header
6. **Copy the entire Cookie header value**

Example cookie format:

```bash
_m_h5_tk=abc123_1234567890; _m_h5_tk_enc=def456; other=cookies...
```

## Examples

### Basic Product Information

```bash
$ python cli.py "https://www.aliexpress.us/item/3256809096800275.html" "cookie_here"

🎯 PRODUCT INFORMATION
==================================================
📝 Title: Automatic Curler 32mm Automatic Rotating Ceramic Curler Professional Curling Wand Curler
🆔 Product ID: 3256809096800275
💰 Price: $9.57 (was $31.27 USD)
⭐ Rating: 5.0 stars (11 sold)
🏪 Store: Shop1104482665 Store (52/100, 96.4 positive)
🚚 Shipping: 2-8 days
    Cost: $2.99 from United States via FEDEX
🖼️ Images: 6 available
```

### Verbose Output

```bash
$ python cli.py --product-id 3256809096800275 --cookie "cookie" --verbose

🔍 Extracted product ID: 3256809096800275
🍪 Cookie length: 3136 characters
🚀 Fetching product data...

🎯 PRODUCT INFORMATION
==================================================
📝 Title: Automatic Curler 32mm Automatic Rotating Ceramic Curler Professional Curling Wand Curler
🆔 Product ID: 3256809096800275
💰 Price: $9.57 (was $31.27 USD)
⭐ Rating: 5.0 stars (11 sold)
🏪 Store: Shop1104482665 Store (52/100, 96.4 positive)
    Country: China
    Open since: Jan 6, 2025
🚚 Shipping: 2-8 days
    Cost: $2.99 from United States via FEDEX
🎨 Available Options:
    Ships From: United States
    Color: black, Yellow, Blue, Pink, WHITE (+ 5 more)
    Plug Type: US
🖼️ Images: 6 available
📊 Data sections available: 25
🔍 API Trace ID: 210156fc17549164996216242ee9d6
```

### JSON Output

```bash
$ python cli.py -p 3256809096800275 -c "cookie" --json

{
  "success": true,
  "product_id": "3256809096800275",
  "title": "Automatic Curler 32mm Automatic Rotating Ceramic Curler Professional Curling Wand Curler",
  "price": {
    "sale_price": "$9.57",
    "original_price": "$31.27",
    "currency": "USD"
  },
  "rating": {
    "score": "5.0",
    "total_sold": "11 sold"
  },
  "store": {
    "name": "Shop1104482665 Store",
    "rating": "52",
    "positive_rate": "96.4"
  },
  ...
}
```

## Error Handling

The CLI provides clear error messages:

```bash
# Missing arguments
$ python cli.py
cli.py: error: Please provide a product URL or ID

# Invalid URL
$ python cli.py "invalid-url" "cookie"
❌ Error: Could not extract product ID from: invalid-url

# Expired cookie
$ python cli.py "valid-url" "expired-cookie"
❌ Error: API error: ['FAIL_SYS_TOKEN_EXOIRED::令牌过期']
```

## Help

Get detailed help information:

```bash
python cli.py --help
```

## Integration

The CLI tool is perfect for:

- **Batch processing** multiple products
- **Shell scripts** and automation
- **Data collection** pipelines
- **Price monitoring** systems
- **API integration** (using JSON output)

Example bash script:

```bash
#!/bin/bash
COOKIE="your_cookie_here"

# Scrape multiple products
for product_id in 3256809096800275 3256808312024826 3256809184052984; do
    echo "Processing product: $product_id"
    python cli.py --product-id "$product_id" --cookie "$COOKIE" --json > "product_${product_id}.json"
    sleep 2  # Be respectful to the API
done
```

## Technical Details

- **Reverse Engineered** from AliExpress JavaScript
- **MTOP API** with proper signature generation  
- **MD5 signature** algorithm
- **JSONP response** parsing
- **Cookie-based** authentication
- **No browser** required (headless)

## Troubleshooting

**Cookie Expired**: Get a fresh cookie from your browser
**Product Not Found**: Check the product ID/URL is correct
**Rate Limiting**: Add delays between requests
**Network Issues**: Check your internet connection

---

🎉 **Ready to scrape AliExpress like a pro!** 🚀
