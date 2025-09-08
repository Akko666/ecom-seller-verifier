from flask import Flask, request, jsonify, render_template
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse # NEW: Import for URL validation

app = Flask(__name__)

# Load verified sellers data
with open('verified_sellers.json', 'r') as f:
    verified_sellers_data = json.load(f)

# --- NEW: Helper function for URL validation ---
def validate_url(link):
    """Checks if the URL is valid and from a supported platform."""
    try:
        parsed_url = urlparse(link)
        # Check for a valid scheme (http/https) and a domain name
        if not all([parsed_url.scheme, parsed_url.netloc]):
            return None, "Invalid URL format. Please enter a full URL (e.g., https://...)."
        
        # Check for supported platforms
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

    # --- UPDATED: Use the new validation function ---
    platform, error_message = validate_url(link)
    if error_message:
        return jsonify({'error': error_message}), 400

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        response = requests.get(link, headers=headers, timeout=10)
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.text, 'html.parser')

        seller_name = None
        if platform == 'amazon':
            # Updated selectors for better reliability
            seller_elem = soup.select_one('#merchant-info a span') or soup.select_one('#sellerProfileTriggerId')
            if seller_elem:
                seller_name = seller_elem.text.strip()
        elif platform == 'flipkart':
            # Updated selectors for better reliability
            seller_elem = soup.select_one('._1RLviY a') or soup.select_one('._3_Fivj')
            if seller_elem:
                seller_name = seller_elem.text.strip()

        if not seller_name:
            # --- UPDATED: More specific error for scraper failure ---
            return jsonify({'error': 'Seller information not found on the page. The site structure may have changed.'}), 404

        # Normalize and check against our list
        seller_name_lower = seller_name.lower()
        is_genuine = any(
            s['seller'].lower() == seller_name_lower and s['platform'] == platform
            for s in verified_sellers_data
        )
        result_status = 'Genuine' if is_genuine else 'Suspicious'

        return jsonify({'seller': seller_name, 'result': result_status})

    # --- UPDATED: More specific exception handling ---
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f"Network error: Could not connect to the website."}), 500
    except Exception as e:
        # Generic catch-all for any other unexpected errors
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
