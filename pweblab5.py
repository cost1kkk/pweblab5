#!/usr/bin/env python

import socket
import ssl
from urllib.parse import urlparse, quote_plus
from bs4 import BeautifulSoup
import re
import argparse
import json
from datetime import datetime
# Defines a function for sending HTTP or HTTPS requests.
def execute_web_request(target_host, target_port, formatted_request, secure=False):
    response_content = None
    try:
        # Establishes a secure SSL connection if required.
        if secure:
            ssl_context = ssl.create_default_context()
            with ssl_context.wrap_socket(socket.socket(), server_hostname=target_host) as secure_socket:
                secure_socket.connect((target_host, target_port))
                secure_socket.sendall(formatted_request.encode())
                response_content = collect_response_data(secure_socket)
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_connection:
                socket_connection.connect((target_host, target_port))
                socket_connection.sendall(formatted_request.encode())
                response_content = collect_response_data(socket_connection)

        return handle_redirection(response_content)
    except Exception as error:
        print(f"Encountered an error during request: {error}")
        return None

# Gathers response data from the server.
def collect_response_data(socket_connection):
    response = b""
    while chunk := socket_connection.recv(4096):
        response += chunk
    return response

# Checks for a 302 redirect and either follows it or returns the response body.
def handle_redirection(response):
    header, _, body = response.partition(b"\r\n\r\n")
    header_lines = header.decode().split("\r\n")
    if "302" in header_lines[0]:  # Checks for redirect status code.
        for line in header_lines:
            if line.startswith("Location:"):
                new_url = line.split(": ", 1)[1]
                return fetch_webpage_content(new_url)
    else:
        return decode_response_content(body)

# Attempts to decode the response content.
def decode_response_content(content):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return content.decode('ISO-8859-1')
        except UnicodeDecodeError:
            print("Failed to decode response content.")
            return None

# Fetches and processes the webpage content from a URL.
def fetch_webpage_content(url):
    url_details = urlparse(url)
    host = url_details.netloc
    scheme = url_details.scheme
    path = url_details.path if url_details.path else "/"

    webpage_identifier = host + path
    cached_data = load_cached_data()
    if webpage_identifier not in cached_data or cache_expired(cached_data[webpage_identifier][0]):
        http_request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        webpage_content = execute_web_request(host, 80 if scheme == "http" else 443, http_request, scheme == "https")
        if webpage_content:
            update_cache(webpage_identifier, webpage_content, cached_data)
    else:
        webpage_content = cached_data[webpage_identifier][1]

    display_content_and_images(webpage_content)

# Loads cached webpage data from a JSON file.
def load_cached_data():
    try:
        with open("data.json", 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Saves updated webpage data to the cache.
def update_cache(identifier, content, cache):
    cache[identifier] = [datetime.now().isoformat(), content]
    with open("data.json", 'w') as file:
        json.dump(cache, file, indent=4)

# Checks if the cached data for a webpage is older than a specified number of seconds.
def cache_expired(timestamp, expiry_seconds=5):
    return (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() > expiry_seconds

# Prints webpage content and lists image sources.
def display_content_and_images(html):
    soup = BeautifulSoup(html, "html.parser")
    clean_text = clean_whitespace(soup.get_text())
    print(clean_text.strip())

    image_sources = [img["src"] for img in soup.find_all('img')]
    if image_sources:
        print("Image sources:")
        for src in image_sources:
            print(src)

# Cleans excessive whitespace from the text.
def clean_whitespace(text):
    text = re.sub(r' +', ' ', text)
    text = text.replace("\n ", "\n").replace("\r\n", "\n")
    text = re.sub(r'\t+', '\t', text)
    text = re.sub(r'\n{2,}', '\n\n', text)
    return re.sub(r'\r{2,}', '\r\r', text)
# Search for terms on Bing and print top 10 results.
def search_with_bing(terms):
    cached_data = load_cached_data()
    search_identifier = "search:" + terms.lower()  # Ensure case-insensitive matching

    if search_identifier in cached_data and not cache_expired(cached_data[search_identifier][0], expiry_seconds=300):
        results = cached_data[search_identifier][1]
    else:
        query = quote_plus(terms)
        content = execute_web_request("www.bing.com", 443,
                                      f"GET /search?q={query} HTTP/1.1\r\nHost: www.bing.com\r\nConnection: close\r\n\r\n",
                                      True)
        if content:
            soup = BeautifulSoup(content, "html.parser")
            results_elements = soup.find(id="b_results").find_all("li", class_="b_algo")
            if not results_elements:
                print(f"No results found for {terms}.")
                return
            results = [{"title": result.find("h2").get_text(), "link": result.find("a")["href"]}
                       for result in results_elements[:10]]
            update_cache(search_identifier, results, cached_data)
        else:
            print("Failed to retrieve or parse search results.")
            return

    for index, result in enumerate(results, start=1):
        print(f"{index}. {result['title']}: {result['link']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web scraper utility.")
    parser.add_argument('-u', '--url', help="Fetches and displays content from the specified URL.")
    parser.add_argument('-s', '--search', help="Searches Bing with the specified terms and displays top results.")
    args = parser.parse_args()

    if args.url:
        fetch_webpage_content(args.url)
    elif args.search:
        search_with_bing(args.search.lower())  # Use lowercase to ensure case-insensitive cache matching
    else:
        print("No action specified. Use -u to fetch URL content or -s to search.")