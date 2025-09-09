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

    print("--- NEW VERIFICATION REQUEST ---") # Log Start
    print(f"Platform identified: {platform}")

    try:
        SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY') 
        if not SCRAPINGBEE_API_KEY:
            return jsonify({'error': 'API key is not configured on the server.'}), 500

        params = {
            'api_key': SCRAPINGBEE_API_KEY,
            'url': link,
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
            seller_elem = soup.select_one('div._3_Fivj a span') or soup.select_one('#sellerName span')
            if seller_elem:
                seller_name = seller_elem.text.strip()

        print(f"1. Scraped raw seller name: '{seller_name}'") # Log Raw Name

        if not seller_name:
            return jsonify({'error': 'Could not find the seller name on the page. The website structure may have changed.'}), 404

        scraped_seller_cleaned = seller_name.lower().replace(" ", "")
        print(f"2. Cleaned scraped name: '{scraped_seller_cleaned}'") # Log Cleaned Scraped Name

        is_genuine = False
        for s in verified_sellers_data:
            if s['platform'] == platform:
                verified_seller_cleaned = s['seller'].lower().replace(" ", "")
                print(f"-> Comparing with DB entry: '{verified_seller_cleaned}'") # Log DB Name
                if scraped_seller_cleaned.startswith(verified_seller_cleaned):
                    print("!!! MATCH FOUND !!!") # Log Match
                    is_genuine = True
                    break 

        print(f"3. Final determination: is_genuine = {is_genuine}") # Log Final Result
        result_status = 'Genuine' if is_genuine else 'Suspicious'
        return jsonify({'seller': seller_name, 'result': result_status})

    except Exception as e:
        print(f"--- ERROR OCCURRED ---: {str(e)}") # Log Errors
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # Use port defined by Render, default to 5000 for local testing
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
