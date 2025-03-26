import os
import re
import requests
import base64
import json
from urllib.parse import urlparse
import fnmatch

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Optional token to handle rate limits

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


def parse_github_url(url):
    url = url.rstrip('/')
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')

    if len(path_parts) < 2:
        raise ValueError("Invalid GitHub URL. Must contain at least owner and repo.")

    owner = path_parts[0]
    repo = path_parts[1]

    if len(path_parts) > 3 and path_parts[2] == 'tree':
        branch = path_parts[3]
        path = '/'.join(path_parts[4:]) if len(path_parts) > 4 else ""
    else:
        branch = "main"
        path = '/'.join(path_parts[3:]) if len(path_parts) > 3 else ""

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "path": path
    }


def should_skip_path(path, skip_patterns):
    for pattern in skip_patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def get_repo_contents(owner, repo, branch="main", path="", skip_patterns=None):
    if skip_patterns is None:
        skip_patterns = []

    all_files = []

    def fetch_contents(path=""):
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code != 200:
            print(f"Error fetching {url}: {response.status_code}")
            print(response.text)
            return

        contents = response.json()
        if not isinstance(contents, list):
            contents = [contents]

        for item in contents:
            item_path = item['path']

            if should_skip_path(item_path, skip_patterns):
                print(f"Skipping: {item_path} (matched skip pattern)")
                continue

            if item['type'] == 'dir':
                fetch_contents(item_path)
            elif item['type'] == 'file':
                if item_path.endswith(('.js', '.jsx', '.ts', '.tsx', '.css', '.scss', '.html', '.md', '.json', '.py', '.txt')):
                    file_response = requests.get(item['url'], headers=HEADERS)

                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        encoded_content = file_data.get('content', '')
                        if file_data.get('encoding') == 'base64':
                            try:
                                content = base64.b64decode(encoded_content).decode('utf-8', errors='replace')
                                all_files.append({
                                    'path': item_path,
                                    'content': content
                                })
                                print(f"Downloaded: {item_path}")
                            except Exception as decode_err:
                                print(f"Failed decoding {item_path}: {decode_err}")
                        else:
                            print(f"Skipped non-base64 encoded file: {item_path}")
                    else:
                        print(f"Error downloading {item_path}: {file_response.status_code}")
                else:
                    print(f"Skipped unsupported file type: {item_path}")

    fetch_contents(path)
    return all_files


def create_markdown(files):
    markdown = "<ReactProject>\n\n"

    for file in files:
        file_path = file['path']
        file_extension = os.path.splitext(file_path)[1][1:]

        file_type = 'tsx' if file_extension in ['tsx', 'jsx', 'ts', 'js'] else file_extension

        markdown += f"{file_type} file=\"{file_path}\"\n<file_codes>\n{file['content']}\n</file_codes>\n\n"

    markdown += "</ReactProject>\n"
    return markdown


def main():
    github_url = "https://github.com/ameerhmzx/language-flash-cards"
    skip_patterns = ["components/ui/*", "node_modules/*"]
    output_file = "output.md"

    try:
        github_info = parse_github_url(github_url)
        print(f"Fetching: {github_info['owner']}/{github_info['repo']}")
        print(f"Branch: {github_info['branch']}")
        print(f"Path: {github_info['path']}")
        print(f"Skip patterns: {skip_patterns}")

        files = get_repo_contents(
            github_info['owner'],
            github_info['repo'],
            github_info['branch'],
            github_info['path'],
            skip_patterns=skip_patterns
        )

        if not files:
            print("No files were downloaded or all files were skipped.")
            return

        markdown = create_markdown(files)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Output written to: {output_file}")
        print(f"Files extracted: {len(files)}")

    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
