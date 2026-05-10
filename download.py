import os
import requests
import zipfile

# ── Configuration ────────────────────────────────────────────────────────
RAW_DIR = "./raw"
os.makedirs(RAW_DIR, exist_ok=True)

# PatentsView AWS S3 Bucket
BASE_URL = "https://s3.amazonaws.com/data.patentsview.org/download/"

# Only the 3 missing files required for your schema
FILES_TO_DOWNLOAD = [
    "g_patent_abstract.tsv.zip",        # Provides the 'abstract'
    "g_patent.tsv.zip",           # Provides the 'title'
    "g_application.tsv.zip",            # Provides 'filing_date' and 'year'
    "g_location_disambiguated.tsv.zip",  # Provides the 'country' for inventors/companies
    "g_cpc_current.tsv.zip",           # Provides the CPC classifications for patents
    "g_assignee_disambiguated.tsv.zip",       # Provides the assignee (company) for each patent
    "g_inventor_disambiguated.tsv.zip",      # Provides the inventor(s) for each patent    
]

# ── Functions ────────────────────────────────────────────────────────────
def download_file(filename):
    url = BASE_URL + filename
    filepath = os.path.join(RAW_DIR, filename)
    print(f"\nConnecting to {url}...")
    
    with requests.get(url, stream=True) as r:
        r.raise_for_status() 
        
        total_size = int(r.headers.get('content-length', 0))
        downloaded_bytes = 0
        
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024): 
                if chunk:
                    f.write(chunk)
                    downloaded_bytes += len(chunk)
                    
                    if total_size > 0:
                        done_percentage = int(50 * downloaded_bytes / total_size)
                        progress_bar = '=' * done_percentage + ' ' * (50 - done_percentage)
                        mb_downloaded = downloaded_bytes / (1024 * 1024)
                        print(f"\r[{progress_bar}] {mb_downloaded:.2f} MB", end='', flush=True)
                        
    print(f"\nDownload complete: {filename}")
    return filepath

def extract_and_cleanup(filepath):
    print(f"Extracting {filepath}...")
    
    with zipfile.ZipFile(filepath, 'r') as zip_ref:
        zip_ref.extractall(RAW_DIR)
    
    os.remove(filepath)
    print(f"Extracted and deleted zip: {filepath}")

def run_download() -> None:
    print("Starting download for missing PatentsView files...")

    for filename in FILES_TO_DOWNLOAD:
        saved_zip_path = download_file(filename)
        extract_and_cleanup(saved_zip_path)

    print("\nPipeline extraction complete. All 6 required .tsv files are now ready in ./raw")


# ── Execution ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_download()