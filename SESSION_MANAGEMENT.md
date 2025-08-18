# Session Management and Cookie Extraction Features

## Overview

This document describes the enhanced session management and cookie extraction features implemented for the AliExpress Store Credentials Network Scraper.

## Features Implemented

### 1. Cookie Extraction for HTTP Requests

#### Sync Method: `get_cookies_for_requests()`

```python
scraper = StoreCredentialsNetworkScraper()
cookies = scraper.get_cookies_for_requests()
# Returns: {"lzd_cid": "862cbdfe-...", "cna": "5KUgIVLeul...", ...}
```

#### Async Method: `get_cookies_for_requests_async()`

```python
scraper = StoreCredentialsNetworkScraper()
cookies = await scraper.get_cookies_for_requests_async()
# Returns: {"lzd_cid": "862cbdfe-...", "cna": "5KUgIVLeul...", ...}
```

**Purpose**: Extract cookies from the active browser session in a simple key-value format suitable for subsequent HTTP requests using libraries like `requests`.

**Format**: Returns `dict[str, str]` where keys are cookie names and values are cookie values.

### 2. Browser Session Reuse with CAPTCHA-Based Restart

#### Constructor Enhancement

```python
scraper = StoreCredentialsNetworkScraper(
    max_captcha_attempts=3,  # New parameter
    # ... other existing parameters
)
```

#### CAPTCHA Failure Tracking

- **Automatic Tracking**: CAPTCHA failures are tracked automatically during scraping
- **Counter Management**: Maintains `captcha_failure_count` vs `max_captcha_attempts`
- **Session State**: Tracks `session_active` status

#### Session Restart Logic

- Browser session continues until CAPTCHA failures reach the threshold
- When `captcha_failure_count >= max_captcha_attempts`:
  1. Current browser and context are closed
  2. New browser session is started
  3. CAPTCHA counter is reset
  4. Session continues with fresh state

### 3. Session Management Methods

#### `_check_session_health() -> bool`

- Verifies browser context is active and functional
- Tests by creating/closing a temporary page
- Returns `True` if session is healthy

#### `_restart_browser_session() -> None`

- Closes current browser/context
- Resets session state and CAPTCHA counters
- Initializes fresh browser session
- Loads saved cookies into new session

#### `_should_restart_session() -> bool`

- Checks if session should be restarted
- Returns `True` when CAPTCHA failures exceed threshold

#### `_increment_captcha_failure() -> None`

- Increments CAPTCHA failure counter
- Logs current failure status
- Warns when max attempts reached

#### `_reset_captcha_counter() -> None`

- Resets CAPTCHA failure counter to 0
- Called after successful operations

### 4. Integration with Existing Session Persistence

The new session management integrates seamlessly with the existing JSON-based session persistence:

- **Cookie Loading**: Saved cookies are automatically loaded into new sessions
- **Cookie Saving**: Successful scraping operations save cookies for future use  
- **Session Continuity**: Browser restarts preserve authentication state through cookie persistence

## Usage Examples

### Basic Usage with Session Management

```python
import asyncio
from store_credentials_network_scraper import StoreCredentialsNetworkScraper

async def scrape_with_session_management():
    # Initialize with session management
    scraper = StoreCredentialsNetworkScraper(
        headless=False,
        max_captcha_attempts=3,  # Restart after 3 CAPTCHA failures
        cookies_file="my_session.json"
    )
    
    store_ids = ["1100230031", "1100228581", "1100229467"]
    
    # Scraping will automatically:
    # 1. Load saved cookies from previous sessions
    # 2. Track CAPTCHA failures during scraping
    # 3. Restart browser when CAPTCHA threshold reached
    # 4. Continue with fresh session and reset counter
    # 5. Save cookies after successful operations
    results = await scraper.scrape_store_credentials(store_ids)
    
    return results

# Run the scraper
results = asyncio.run(scrape_with_session_management())
```

### Extract Cookies for HTTP Requests

```python
import requests
from store_credentials_network_scraper import StoreCredentialsNetworkScraper

async def use_cookies_for_http():
    scraper = StoreCredentialsNetworkScraper()
    
    # After some scraping to establish session...
    await scraper.scrape_store_credentials(["1100230031"])
    
    # Extract cookies for HTTP requests
    cookies = scraper.get_cookies_for_requests()
    
    # Use with requests library
    response = requests.get(
        "https://aliexpress.com/some-api-endpoint",
        cookies=cookies,
        headers={"User-Agent": scraper.user_agent}
    )
    
    return response.json()
```

## Configuration Options

### Constructor Parameters

- `max_captcha_attempts: int = 3`: Maximum CAPTCHA solve attempts before browser restart
- `cookies_file: str = "aliexpress_session_cookies.json"`: Path to session persistence file

### Session Management Behavior

1. **Normal Operation**: Browser session stays active across multiple store requests
2. **CAPTCHA Detection**: Each CAPTCHA solve failure increments counter
3. **Threshold Reached**: When failures >= max_attempts, browser restarts automatically
4. **Counter Reset**: Successful operations or manual reset clears failure count
5. **Session Restoration**: New sessions automatically load saved cookies

## Testing

### Quick Test (No Dependencies)

```bash
python3 quick_test_session.py
```

### Full Test (Requires Dependencies)

```bash
# Install dependencies first
pip install playwright python-dotenv

# Run full browser test
python3 test_session_management.py
```

## Benefits

1. **Improved Reliability**: Automatic session restart prevents prolonged CAPTCHA blocking
2. **Efficient Resource Usage**: Browser stays active for multiple requests when possible
3. **Authentication Preservation**: Cookie persistence maintains login state across restarts
4. **HTTP Integration**: Easy cookie extraction for use with other HTTP libraries
5. **Configurable Behavior**: Adjustable CAPTCHA tolerance and session parameters

## Technical Implementation

### Session State Tracking

```python
# Instance variables added to class
self.max_captcha_attempts = max_captcha_attempts
self.captcha_failure_count = 0
self.session_active = False
```

### CAPTCHA Handling Integration

```python
# In _scrape_single_store method
if captcha_solved:
    self._reset_captcha_counter()  # Reset on success
else:
    self._increment_captcha_failure()  # Track failure
```

### Main Loop Session Management

```python
# In scrape_store_credentials method
for store_id in store_ids:
    # Check if restart needed
    if self._should_restart_session():
        await self._restart_browser_session()
    
    # Verify session health
    if not await self._check_session_health():
        await self._restart_browser_session()
    
    # Continue with scraping...
```

## Error Handling

- **Session Restart Failures**: Logged as errors, scraping continues with existing session
- **Health Check Failures**: Triggers restart attempt, continues if restart fails
- **Cookie Extraction Failures**: Returns empty dict, logs warning
- **Browser Context Errors**: Proper null checks prevent crashes

This implementation provides robust session management while maintaining backward compatibility with existing functionality.
