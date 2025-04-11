from flask import Flask, request, render_template_string
from PIL import Image
import pytesseract
import io
import requests
from bs4 import BeautifulSoup
import os
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")

app = Flask(__name__)

HTML_PAGE = """<!doctype html>
<html>
<head>
    <title>Bookshelf OCR Scanner</title>
    <style>
        body { font-family: Arial; padding: 40px; }
        input[type=file] { margin: 20px 0; }
        .book { margin-bottom: 15px; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>📚 Bookshelf OCR</h1>
    <p>Upload a photo of book spines and get book titles with Amazon links.</p>
    <form method="post" enctype="multipart/form-data" action="/upload">
        <input type="file" name="image" accept="image/*" required>
        <br>
        <button type="submit">Upload Image</button>
    </form>
</body>
</html>"""

# --- OCR Text Extraction ---
def extract_books_from_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return lines

# --- AI Cleanup ---
def clean_book_list_with_ai(raw_lines):
    prompt = "Extract book titles and authors from the following OCR results:\n\n" + "\n".join(raw_lines) + "\n\nFormat: Title - Author"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        cleaned_text = response.choices[0].message["content"]
        return [line.strip() for line in cleaned_text.split("\n") if line.strip()]
    except Exception as e:
        return [f"Error during AI cleanup: {e}"]

# --- Amazon Search Link ---
def search_amazon_links(query):
    search_url = f"https://www.amazon.com/s?k={requests.utils.quote(query)}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    result = soup.find('a', class_='a-link-normal s-no-outline')
    if result and 'href' in result.attrs:
        return f"https://www.amazon.com{result['href']}"
    return None

# --- Web Routes ---
@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return 'No image uploaded', 400

    image = request.files['image'].read()
    raw_lines = extract_books_from_image(image)
    lines = clean_book_list_with_ai(raw_lines)

    results = []
    for line in lines:
        link = search_amazon_links(line)
        results.append({'text': line, 'amazon_link': link})

    result_html = '<h1>Results</h1>'
    for r in results:
        result_html += '<div class="book">'
        result_html += f"<strong>{r['text']}</strong><br>"
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
