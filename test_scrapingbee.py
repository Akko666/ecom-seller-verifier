import requests
import os

# Best Practice: Load the key from environment variables, just like in app.py
SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY') 

if not SCRAPINGBEE_API_KEY:
    print("Error: SCRAPINGBEE_API_KEY is not set as an environment variable.")
else:
    link = "https://www.flipkart.com/realme-p2-pro-5g-parrot-green-256-gb/p/itm53d39fff9f20c?pid=M"
    params = {
        'api_key': SCRAPINGBEE_API_KEY,
        'url': link,
        'premium_proxy': 'true',
        'country_code': 'in'
    }
    try:
        print(f"Attempting to fetch {link} via ScrapingBee...")
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)
        response.raise_for_status()
        print("ScrapingBee response status:", response.status_code)
        print("ScrapingBee response text (first 500 chars):", response.text[:500])
    except requests.exceptions.RequestException as e:
        print(f"Network error during ScrapingBee request: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")