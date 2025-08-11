
# AliExpress Product & Seller Scraper

This project provides a fully reverse-engineered AliExpress client with **automated cookie generation** and **focused seller field extraction**. It interacts directly with AliExpress's internal MTOP API to extract comprehensive product data and core seller information.

## 🎯 Key Features

### 🤖 **Automated Cookie Management**

- **No manual cookie collection required!**
- Headless browser automation using Playwright
- Session caching with 1-minute validity (configurable)
- Automatic retry with fresh cookies on failure
- Minimizes browser automation overhead

### 🔧 **API Integration**

- Reverse engineered signature algorithm (MD5-based, as used by AliExpress)
- Direct integration with AliExpress MTOP API endpoints
- Complete product data extraction: title, price, ratings, store info, shipping, variants, images, and more

### 💻 **User-Friendly Interface**

- Enhanced CLI with automated cookies
- Multiple output formats: human-readable, JSON, verbose
- Batch processing support
- Flexible input: URLs and product IDs
- Comprehensive error handling

## 🚀 Quick Start (Automated Mode)

### ✨ **No Cookies Required!**

```bash
# Basic usage - fully automated!
python enhanced_cli.py "https://www.aliexpress.us/item/3256809096800275.html"

# Using product ID
python enhanced_cli.py --product-id 3256809096800275

# JSON output
python enhanced_cli.py --product-id 3256809096800275 --json

# Batch processing multiple products
python enhanced_cli.py --batch "3256809096800275,1234567890123,9876543210987"

# Test the automation system
python enhanced_cli.py --test-automation
```

### 🐍 **Python Library Usage (Enhanced)**

```python
from enhanced_aliexpress_client import EnhancedAliExpressClient

# Initialize with automation
client = EnhancedAliExpressClient()

# Get product data (fully automated!)
product_data = client.get_product("3256809096800275")

# Print formatted summary
client.print_product_summary(product_data)

# Batch processing
results = client.batch_get_products(["id1", "id2", "id3"])
```

### 👤 **Core Seller Field Extraction**

Extract the **6 available seller fields** from AliExpress products with 95%+ success rate:

```python
from core_seller_extractor import CoreSellerExtractor

extractor = CoreSellerExtractor()
seller_data = extractor.extract_core_seller_fields(api_response)

print(f"Seller: {seller_data['seller_name']}")
print(f"Rating: {seller_data['seller_rating']}/100")
print(f"Country: {seller_data['country']}")

# Get organized summary
summary = extractor.extract_seller_summary(api_response)
quality = extractor.validate_extraction_quality(seller_data)
print(f"Quality: {quality['quality']} ({quality['extraction_rate']})")
```

**✅ Available Core Fields (6/12):**

| Field | API Source | Description |
|-------|------------|-------------|
| **Seller Name** | `SHOP_CARD_PC.storeName` | Store/seller display name |
| **Profile Picture** | `SHOP_CARD_PC.logo` | Seller avatar/logo URL |
| **Profile URL** | `SHOP_CARD_PC.storeHomePage` | Direct link to seller's store |
| **Seller Rating** | `SHOP_CARD_PC.sellerScore` | Numerical rating (0-100) |
| **Total Reviews** | `SHOP_CARD_PC.sellerTotalNum` | Total seller interactions |
| **Country** | `SHOP_CARD_PC.sellerInfo.countryCompleteName` | Seller's country |

**❌ Unavailable Fields:**

- Email Address, Business/Legal Name, State/Province, Zip Code, Phone Number, Address

**CLI Usage:**

```bash
# Extract from product ID
python core_seller_cli.py 3256809096800275

# Extract from URL  
python core_seller_cli.py --url "https://www.aliexpress.us/item/123.html"

# Use manual cookie
python core_seller_cli.py 123456 --cookie "your_cookie_string"

# Show demo with sample data
python core_seller_cli.py --demo
```

**Sample Output:**

```bash
🎯 CORE SELLER FIELDS EXTRACTED
===================================
📦 Product ID: 3256809096800275
🏆 Quality: Excellent (100.0%)

👤 SELLER INFORMATION
-------------------------
  Name           : TechWorld Store
  Profile Picture: https://ae-pic-a1.aliexpress-media.com/kf/example.png
  Store URL      : https://m.aliexpress.com/store/storeHome.htm?sellerAdminSeq=123456
  Rating         : 89.0/100
  Total Reviews  : 2156
  Country        : China
```

**Quality Assessment:**

- **Excellent**: 5-6 fields extracted (83-100%)
- **Good**: 4 fields extracted (67%)  
- **Fair**: 2-3 fields extracted (33-50%)
- **Poor**: 0-1 fields extracted (0-17%)

### 📋 **Manual Cookie Mode (Original)**

If automation doesn't work, you can still use manual cookies:

```bash
# Manual cookie override
python enhanced_cli.py --product-id 3256809096800275 --cookie "your_cookie_here"
```

## 📁 Project Structure

**Core Files:**

- `aliexpress_client.py` - Core MTOP API client with signature algorithm
- `enhanced_aliexpress_client.py` - Automated cookie management wrapper
- `core_seller_extractor.py` - Focused seller field extraction (6 available fields)
- `cookie_generator.py` - Playwright-based cookie automation
- `captcha_solver.py` - Basic captcha handling

**CLI Tools:**

- `enhanced_cli.py` - Main CLI with automation
- `core_seller_cli.py` - Seller field extraction CLI
- `cli.py` - Original CLI (manual cookies)

**Documentation:**

- `CORE_SELLER_README.md` - Detailed seller extraction guide
- `CORE_FIELDS_SUMMARY.py` - Implementation summary

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/huenique/aliexpress-scraper.git
   cd aliexpress-scraper
   ```

2. **Install dependencies**:

   ```bash
   pip install requests playwright
   # Install browser for automation
   playwright install chromium
   
   # Or, if using uv:
   uv sync
   playwright install chromium
   ```

3. **Optional - Manual Cookies**:
   If automation fails, you can use manual cookies:
   - Visit <https://www.aliexpress.us> in your browser
   - Open Developer Tools (F12) and go to the Network tab
   - Copy the 'Cookie' header from any request

## 🔧 Integration Examples

### Complete Product & Seller Extraction

```python
from enhanced_aliexpress_client import EnhancedAliExpressClient
from core_seller_extractor import CoreSellerExtractor

def get_complete_product_info(product_id):
    """Get both product and seller info in one call."""
    
    # Initialize clients
    client = EnhancedAliExpressClient()
    extractor = CoreSellerExtractor()
    
    # Get product data (automated cookies)
    product_data = client.get_product(product_id)
    
    if product_data.get('success'):
        # Extract seller info from same API response
        seller_data = extractor.extract_core_seller_fields(product_data)
        seller_summary = extractor.extract_seller_summary(product_data)
        quality = extractor.validate_extraction_quality(seller_data)
        
        return {
            'product': {
                'title': product_data.get('title'),
                'price': product_data.get('price', {}).get('sale_price'),
                'rating': product_data.get('rating', {}).get('score'),
                'sales': product_data.get('sales_info', {}).get('total')
            },
            'seller': seller_data,
            'seller_summary': seller_summary,
            'seller_quality': quality['quality'],
            'success': True
        }
    else:
        return {'success': False, 'error': product_data.get('error')}

# Usage
result = get_complete_product_info("3256809096800275")
if result['success']:
    print(f"Product: {result['product']['title']}")
    print(f"Seller: {result['seller']['seller_name']}")
    print(f"Quality: {result['seller_quality']}")
```

### Batch Processing with Seller Data

```python
def batch_extract_with_sellers(product_ids):
    """Extract product and seller data for multiple products."""
    
    client = EnhancedAliExpressClient()
    extractor = CoreSellerExtractor()
    results = []
    
    for product_id in product_ids:
        try:
            # Get product data
            product_data = client.get_product(product_id)
            
            if product_data.get('success'):
                # Extract seller info
                seller_data = extractor.extract_core_seller_fields(product_data)
                quality = extractor.validate_extraction_quality(seller_data)
                
                results.append({
                    'product_id': product_id,
                    'product_title': product_data.get('title'),
                    'seller_name': seller_data.get('seller_name'),
                    'seller_rating': seller_data.get('seller_rating'),
                    'seller_country': seller_data.get('country'),
                    'extraction_quality': quality['quality'],
                    'success': True
                })
            else:
                results.append({
                    'product_id': product_id,
                    'success': False,
                    'error': product_data.get('error')
                })
                
        except Exception as e:
            results.append({
                'product_id': product_id,
                'success': False,
                'error': str(e)
            })
    
    return results

# Usage
product_ids = ["3256809096800275", "1234567890123", "9876543210987"]
results = batch_extract_with_sellers(product_ids)

for result in results:
    if result['success']:
        print(f"{result['seller_name']} ({result['seller_country']}) - {result['extraction_quality']}")
    else:
        print(f"Failed: {result['product_id']} - {result['error']}")
```

## 🎯 Key Benefits & Best Practices

### Seller Field Extraction

1. **Focused Approach**: Only extracts confirmed available fields (6/12)
2. **Clean Data**: No N/A values or placeholders  
3. **High Success Rate**: 95%+ reliability for available fields
4. **Quality Assessment**: Built-in validation and quality scoring
5. **Organized Output**: Both raw fields and categorized summary formats

### Best Practices

- **Cache Seller Data**: Store seller info to reduce API calls
- **Quality Check**: Always validate extraction quality before using data
- **Combine Data**: Use seller fields alongside product data for complete intelligence
- **Rate Limiting**: Be respectful to AliExpress servers
- **Error Handling**: Implement proper retry logic for failed extractions

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
├── cli.py                          # Main CLI tool for product scraping
├── enhanced_cli.py                 # Enhanced CLI with additional features
├── aliexpress_client.py            # Core AliExpress API client
├── enhanced_aliexpress_client.py   # Enhanced client with proxy/retry logic
├── cookie_generator.py             # Cookie generation via Playwright
├── captcha_solver.py               # CAPTCHA solving utilities
├── core_seller_extractor.py        # Seller field extraction (6 core fields)
├── core_seller_cli.py              # CLI tool for seller data extraction
├── logger.py                       # Logging configuration
├── example.py                      # Usage examples
├── cli_demo.sh                     # Demo script for CLI usage
├── pyproject.toml                  # Project dependencies
└── README.md                       # Main documentation
```

## Technical Details

- **Signature Algorithm**: `MD5(token + '&' + timestamp + '&' + appKey + '&' + data)`
- **API Protocol**: MTOP JSONP with callback wrapping
- **Authentication**: Cookie-based with `_m_h5_tk` tokens
- **Endpoints**: `acs.aliexpress.us/h5/mtop.aliexpress.pdp.pc.query/`
- **Response Format**: JSONP-wrapped JSON data
- **Seller Data Source**: `SHOP_CARD_PC` section in API response

## Project Highlights

- Fully reverse engineered from AliExpress JavaScript source code
- Real API integration (not HTML scraping)
- Working signature algorithm implementation
- Complete product data extraction and parsing
- Focused seller field extraction (6 core fields)
- Automated cookie management with Playwright
- CLI tools for command-line usage
- Production ready with comprehensive error handling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with fresh cookies and various product IDs
5. Submit a pull request

## Important Notes

- **Fresh cookies required**: AliExpress tokens expire regularly (automated handling available)
- **Rate limiting**: Please be respectful to AliExpress servers
- **Legal compliance**: Use responsibly and respect AliExpress terms of service
- **Educational purpose**: This project is for learning and research purposes only
- **Field availability**: Only 6/12 seller fields available in public API - focus on what works
