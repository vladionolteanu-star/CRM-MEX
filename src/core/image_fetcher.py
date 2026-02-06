"""
Image URL Fetcher with Caching
Extracts og:image from Mobexpert product pages on demand.
Uses st.cache_data for persistence across reruns.
"""
import requests
import re
from typing import Optional, Dict
import streamlit as st

# In-memory cache to avoid repeated requests within same session
_image_cache: Dict[str, Optional[str]] = {}

def fetch_og_image(product_url: str, timeout: int = 5) -> Optional[str]:
    """
    Fetch og:image from a Mobexpert product page.
    
    Args:
        product_url: URL like https://mobexpert.ro/products/xyz
        timeout: Request timeout in seconds
        
    Returns:
        Direct image URL or None if not found
    """
    if not product_url or product_url in ('#null', 'nan', ''):
        return None
    
    # Check in-memory cache first
    if product_url in _image_cache:
        return _image_cache[product_url]
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(product_url, headers=headers, timeout=timeout)
        content = r.text
        
        # Try og:image first
        match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', content)
        if match:
            img_url = match.group(1)
            _image_cache[product_url] = img_url
            return img_url
        
        # Try og:image:secure_url
        match = re.search(r'<meta\s+content="([^"]+)"\s+property="og:image"', content)
        if match:
            img_url = match.group(1)
            _image_cache[product_url] = img_url
            return img_url
            
        # Fallback: any Shopify CDN image
        match = re.search(r'(https://cdn\.shopify\.com/s/files/[^"\'>\s]+\.(?:jpg|png|webp))', content, re.I)
        if match:
            img_url = match.group(1)
            _image_cache[product_url] = img_url
            return img_url
        
        _image_cache[product_url] = None
        return None
        
    except Exception as e:
        print(f"[ImageFetcher] Error fetching {product_url}: {e}")
        _image_cache[product_url] = None
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_product_image_cached(product_url: str) -> Optional[str]:
    """
    Cached version of fetch_og_image.
    Cache persists for 1 hour across reruns.
    """
    return fetch_og_image(product_url)


def batch_fetch_images(product_urls: list, max_concurrent: int = 5) -> Dict[str, Optional[str]]:
    """
    Fetch images for multiple products.
    Limited to avoid overwhelming the server.
    
    Args:
        product_urls: List of product page URLs
        max_concurrent: Max URLs to fetch in one batch
        
    Returns:
        Dict mapping URL to image URL
    """
    results = {}
    
    # Only fetch first N to avoid slow page load
    to_fetch = [u for u in product_urls if u and u not in _image_cache][:max_concurrent]
    
    for url in to_fetch:
        results[url] = fetch_og_image(url)
    
    # Add cached results
    for url in product_urls:
        if url in _image_cache:
            results[url] = _image_cache[url]
    
    return results


def clear_image_cache():
    """Clear the in-memory image cache."""
    global _image_cache
    _image_cache = {}
