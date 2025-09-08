from flask import Flask, request, jsonify, render_template
import json
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Load verified sellers data
with open('verified_sellers.json', 'r') as f:
    verified_sellers = json.load(f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    link = data.get('link')
    if not link:
        return jsonify({'error': 'No link provided'}), 400

    platform = None
    if 'amazon' in link.lower():
        platform = 'amazon'
    elif 'flipkart' in link.lower():
        platform = 'flipkart'
    else:
        return jsonify({'error': 'Unsupported platform'}), 400

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(link, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        seller_elem = None
        if platform == 'amazon':
            seller_elem = soup.find('a', id='sellerName')
        elif platform == 'flipkart':
            seller_elem = soup.find(id='sellerName')

        if not seller_elem:
            return jsonify({'seller': 'Not found', 'result': 'Suspicious'})

        seller_name = seller_elem.get_text(strip=True)

        # Check if seller is genuine
        seller_lower = seller_name.lower()
        is_genuine = any(
            s['seller'].lower() == seller_lower and s['platform'] == platform
            for s in verified_sellers
        )
        result = 'Genuine' if is_genuine else 'Suspicious'

        return jsonify({'seller': seller_name, 'result': result})

    except requests.RequestException as e:
        return jsonify({'error': f'Failed to fetch page: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
