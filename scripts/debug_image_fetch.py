import requests
import re
import sys

def get_image(url):
    print(f"Fetching {url}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=10)
        content = r.text
        
        # Look for og:image
        match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', content)
        if match:
            return match.group(1)
            
        # Look for secure_url
        match = re.search(r'<meta\s+property="og:image:secure_url"\s+content="([^"]+)"', content)
        if match:
            return match.group(1)

        # Fallback: Look for any shopify cdn image
        match = re.search(r'//cdn\.shopify\.com/s/files/[^"]+?\.jpg', content)
        if match:
             return "https:" + match.group(0) if match.group(0).startswith("//") else match.group(0)

        return "No image found"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    url = "https://mobexpert.ro/products/dealidago090-alida-covor?variant=51953491411273"
    print(get_image(url))
