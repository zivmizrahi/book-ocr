from flask import Flask, request, render_template_string
import openai
import os
import base64
import requests
from bs4 import BeautifulSoup

openai.api_key = os.environ.get("OPENAI_API_KEY")

app = Flask(__name__)

HTML_PAGE = """<!doctype html>
<html>
<head>
    <title>Bookshelf OCR with GPT-4-Vision</title>
    <style>
        body { font-family: Arial; padding: 40px; }
        input[type=file] { margin: 20px 0; }
        .book { margin-bottom: 15px; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>📚 GPT-4 Vision Bookshelf Scanner</h1>
    <p>Upload a photo of book spines and get book titles, ratings, and Amazon links.</p>
    <form method="post" enctype="multipart/form-data" action="/upload">
        <input type="file" name="image" accept="image/*" required>
        <br>
        <button type="submit">Upload Image</button>
    </form>
</body>
</html>"""

def extract_books_from_image_gpt4(image_bytes):
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    image_url = f"data:image/jpeg;base64,{image_base64}"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "From this bookshelf photo, extract a list of book titles and their authors. Format like this: 'Title - Author' per line."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=1000,
        )
        cleaned_text = response.choices[0].message["content"]
        return [line.strip() for line in cleaned_text.split("\n") if line.strip()]
    except Exception as e:
        return [f"Error during GPT-4 Vision processing: {e}"]

def search_amazon_links(query):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import unquote

    search_url = f"https://www.google.com/search?q=site:amazon.com+{requests.utils.quote(query)}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']
            if "/url?q=" in href and "amazon.com" in href:
                raw_url = href.split("/url?q=")[1].split("&")[0]
                clean_url = unquote(raw_url)

                try:
                    product_response = requests.get(clean_url, headers=headers, timeout=10)
                    product_soup = BeautifulSoup(product_response.text, 'html.parser')
                    rating_span = product_soup.find('span', {'class': 'a-icon-alt'})
                    rating = rating_span.get_text(strip=True) if rating_span else "⭐️ No rating"
                except Exception:
                    rating = "⭐️ Error fetching rating"

                return clean_url, rating

    except Exception:
        pass

    return None, "⭐️ No link found", "⭐️ No link found", "⭐️ No link found"

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return 'No image uploaded', 400

    image_bytes = request.files['image'].read()
    lines = extract_books_from_image_gpt4(image_bytes)

    results = []
    for line in lines:
        link, rating = search_amazon_links(line)
        results.append({'text': line, 'amazon_link': link, 'rating': rating})

    result_html = '<h1>Results</h1>'
    for r in results:
        result_html += '<div class="book">'
        result_html += f"<strong>{r['text']}</strong><br>"
        result_html += f"{r['rating']}<br>"
        if r['amazon_link']:
            result_html += f"<a href='{r['amazon_link']}' target='_blank'>View on Amazon</a>"
        else:
            result_html += "<em>No link found</em>"
        result_html += '</div>'

    result_html += '<br><a href="/">🔙 Upload another image</a>'
    return render_template_string(result_html)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
