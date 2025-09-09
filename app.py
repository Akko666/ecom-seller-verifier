from flask import Flask, request, jsonify, render_template
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import os
import re # Import the regular expression module

app = Flask(__name__)

# Load verified sellers data
with open('verified_sellers.json', 'r') as f:
    verified_sellers_data = json.load(f)

def clean_and_validate_url(text):
    """
    Extracts, cleans, and validates the first Amazon/Flipkart URL from a text block.
    This is the Python equivalent of the frontend JavaScript cleaner.
    """
    if not text:
        return None, "URL is empty."

    # Regex to find potential URLs
    url_regex = re.compile(r'https?:\/\/[^\s/$.?#].[^\s]*|www\.[^\s/$.?#].[^\s]*', re.IGNORECASE)
    matches = url_regex.findall(text)

    if not matches:
        return None, "No valid URL found in the provided text."

    for match in matches:
        try:
            url_string = match if match.startswith('http') else f"https://{match}"
            parsed_url = urlparse(url_string)

            # Check for supported platforms
            hostname = parsed_url.hostname.lower() if parsed_url.hostname else ''
            if 'amazon' not in hostname and 'flipkart' not in hostname:
                continue # Not a supported platform, try the next match

            # Define tracking parameters to remove
            params_to_remove = [
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'ref', 'ref_', 'affid', 'affExtParam1',
                'smid', '_encoding', 'psc'
            ]
            
            query_params = parse_qs(parsed_url.query)
            # Filter out the unwanted parameters
            clean_params = {
                k: v for k, v in query_params.items() 
                if not any(k.startswith(param) for param in params_to_remove)
            }

            # Reconstruct the URL with cleaned query parameters
            # Use urlunparse to correctly reassemble the URL components
            url_parts = list(parsed_url)
            url_parts[4] = urlencode(clean_params, doseq=True) # Index 4 is the query string
            
            return urlunparse(url_parts), None # Return the cleaned URL and no error

        except Exception:
            # Ignore malformed URLs and continue
            continue
    
    return None, "Could not find a valid Amazon or Flipkart URL."


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/verify', methods=['POST'])
def verify():
    link = request.json.get('link')
    
    cleaned_link, error_message = clean_and_validate_url(link)
    
    if error_message:
        return jsonify({'error': error_message}), 400

    platform = 'amazon' if 'amazon' in urlparse(cleaned_link).hostname else 'flipkart'

    try:
        SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY') 
        if not SCRAPINGBEE_API_KEY:
            return jsonify({'error': 'API key is not configured on the server.'}), 500

        params = {
            'api_key': SCRAPINGBEE_API_KEY,
            'url': cleaned_link,
            'premium_proxy': 'true',
            'country_code': 'in'
        }
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        seller_name = None
        if platform == 'amazon':
            seller_elem = soup.select_one('#merchant-info a span') or soup.select_one('#sellerProfileTriggerId')
            if seller_elem:
                seller_name = seller_elem.text.strip()
        elif platform == 'flipkart':
            seller_elem = soup.select_one('div._3_Fivj a span') or soup.select_one('#sellerName span span')
            if seller_elem:
                seller_name = seller_elem.text.strip()

        if not seller_name:
            return jsonify({'error': 'Could not find the seller name on the page. The website structure may have changed.'}), 404

        scraped_seller_cleaned = seller_name.lower().replace(" ", "")

        is_genuine = False
        for s in verified_sellers_data:
            if s['platform'] == platform:
                verified_seller_cleaned = s['seller'].lower().replace(" ", "")
                if scraped_seller_cleaned.startswith(verified_seller_cleaned):
                    is_genuine = True
                    break 

        if not is_genuine:
            # --- NEW: Suspicious Seller Logic ---
            # 1. Extract Product Title
            product_title = None
            if platform == 'amazon':
                title_elem = soup.select_one('#productTitle')
                if title_elem:
                    product_title = title_elem.text.strip()
            elif platform == 'flipkart':
                title_elem = soup.select_one('span.B_NuCI') # Modern Flipkart title selector
                if title_elem:
                    product_title = title_elem.text.strip()
            
            product_title = product_title if product_title else 'this product'

            # 2. Detect Brand from Title
            title_lower = product_title.lower()
            detected_brand = None
            # Map sub-brands/aliases to a primary brand name
            brand_families = {
                'realme': ['realme'],
                'samsung': ['samsung'],
                'xiaomi': ['xiaomi', 'redmi', 'poco'] 
            }

            for primary_brand, aliases in brand_families.items():
                for alias in aliases:
                    if f' {alias} ' in f' {title_lower} ' or title_lower.startswith(alias + ' '):
                        detected_brand = primary_brand
                        break
                if detected_brand:
                    break
            
            # 3. Get Genuine Seller Suggestions
            suggestions = []
            if detected_brand:
                suggestions = [
                    s['seller'] for s in verified_sellers_data
                    if s['platform'] == platform and s.get('brands') and detected_brand in s['brands']
                ]

            # 4. Fallback to general sellers if no brand-specific ones are found
            if not suggestions:
                suggestions = [
                    s['seller'] for s in verified_sellers_data if s['platform'] == platform
                ]
            
            # Limit to 5 unique suggestions
            final_suggestions = list(dict.fromkeys(suggestions))[:5]

            return jsonify({
                'seller': seller_name,
                'result': 'Suspicious',
                'product_title': product_title,
                'genuine_sellers': final_suggestions if final_suggestions else None
            })
        
        # --- Original logic for genuine sellers ---
        return jsonify({'seller': seller_name, 'result': 'Genuine'})

    except Exception as e:
        print(f"--- ERROR OCCURRED ---: {str(e)}") 
        return jsonify({'error': f"An unexpected error occurred while processing the link."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
