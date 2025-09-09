from flask import Flask, request, jsonify, render_template
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os # Make sure os is imported

app = Flask(__name__)

# Load verified sellers data
with open('verified_sellers.json', 'r') as f:
    verified_sellers_data = json.load(f)

def validate_url(link):
    """Checks if the URL is valid and from a supported platform."""
    try:
        parsed_url = urlparse(link)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            return None, "Invalid URL format. Please enter a full URL (e.g., https://...)."
        
        if 'amazon' in parsed_url.netloc:
            return 'amazon', None
        elif 'flipkart' in parsed_url.netloc:
            return 'flipkart', None
        else:
            return None, "Unsupported platform. Please use a link from Amazon or Flipkart."
    except Exception:
        return None, "An error occurred while parsing the URL."

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    link = request.json.get('link')
    if not link:
        return jsonify({'error': 'No link provided.'}), 400

    platform, error_message = validate_url(link)
    if error_message:
        return jsonify({'error': error_message}), 400

    try:
        # --- FIX: Load API Key from Render's Environment Variables ---
        SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY') 
        
        if not SCRAPINGBEE_API_KEY:
            # This error will show if the key isn't set on Render
            return jsonify({'error': 'API key is not configured on the server.'}), 500

        params = {
            'api_key': SCRAPINGBEE_API_KEY,
            'url': link,
            'premium_proxy': 'true',
            'country_code': 'in'
        }

        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)
        response.raise_for_status()

        if response.status_code != 200:
            return jsonify({'error': f"Scraping service error: Status {response.status_code}, {response.text}"}), 500

        soup = BeautifulSoup(response.text, 'html.parser')

        seller_name = None
        if platform == 'amazon':
            # Amazon selector (seems okay, but let's keep it robust)
            seller_elem = soup.select_one('#merchant-info a span') or soup.select_one('#sellerProfileTriggerId')
            if seller_elem:
                seller_name = seller_elem.text.strip()
        elif platform == 'flipkart':
            # --- FIX: Updated Flipkart Seller Selector ---
            # Flipkart's seller name is often in a div with a specific ID or class. This is a more reliable selector.
            seller_elem = soup.select_one('div._3_Fivj a span') or soup.select_one('#sellerName span')
            if seller_elem:
                seller_name = seller_elem.text.strip()

        if not seller_name:
            return jsonify({'error': 'Could not find the seller name on the page. The website structure may have changed.'}), 404

        # --- FIX: More flexible seller name matching ---
        
        # 1. Clean the scraped seller name by removing spaces and making it lowercase.
        scraped_seller_cleaned = seller_name.lower().replace(" ", "")

        # 2. Loop through our verified list to find a match.
        is_genuine = False
        for s in verified_sellers_data:
            # Clean the seller name from our JSON file
            verified_seller_cleaned = s['seller'].lower().replace(" ", "")
            
            # Check if the platform matches AND if the scraped name STARTS WITH our verified name
            if s['platform'] == platform and scraped_seller_cleaned.startswith(verified_seller_cleaned):
                is_genuine = True
                break # We found a match, so we can stop checking.

        result_status = 'Genuine' if is_genuine else 'Suspicious'

        return jsonify({'seller': seller_name, 'result': result_status})

    except requests.exceptions.Timeout:
        return jsonify({'error': "The request timed out. The website may be slow to respond."}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({'error': "Network error: Could not connect to the scraping service."}), 500
    except Exception as e:
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # Use port defined by Render, default to 5000 for local testing
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
