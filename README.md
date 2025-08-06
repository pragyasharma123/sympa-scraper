---

# 🤖 sympa-scraper

This project automates the scraping, filtering, and keyword extraction of archived messages from the [Robotics-Worldwide mailing list](https://www.lists.kit.edu/sympa/arc/robotics-worldwide).
It identifies messages related to Human-Robot Interaction (HRI) based on NLP and keyword matching, with the option to **add custom keywords from the command line**.
The results are saved as a structured CSV file and can optionally be uploaded to **MongoDB Atlas** for cloud-based storage and querying.

---

## 📂 Project Structure

| File                       | Purpose                                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `collect_all_messages.py`  | Collects all individual message URLs from the archive                                                        |
| `hri_analyze_messages.py`  | Parses message HTML, extracts metadata, applies NLP, filters using built-in and custom keywords, outputs CSV |
| `upload_to_mongodb.py`     | Uploads the CSV output to a MongoDB Atlas cluster                                                            |
| `all_message_links.txt`    | List of all message URLs from the archive                                                                    |
| `hri_analysis_summary.csv` | Final analysis results: sender, subject, institution, keywords, etc.                                         |

---

## 🔧 Requirements

* Python 3.8+
* [Playwright](https://playwright.dev/python/)
* [spaCy](https://spacy.io/)
* BeautifulSoup (`bs4`)
* [pymongo](https://pypi.org/project/pymongo/) (for MongoDB upload)
* pandas

Install dependencies:

```bash
pip install playwright bs4 spacy pandas "pymongo[srv]==3.11"
python -m playwright install
python -m spacy download en_core_web_sm
```

---

## 🚀 Usage

### **Step 1: Scrape All Message Links**

```bash
python collect_all_messages.py
```

* Opens the Robotics-Worldwide archive.
* Bypasses the anti-spam confirmation.
* Collects monthly archive URLs.
* Extracts individual message URLs.
* Saves them to `all_message_links.txt`.

---

### **Step 2: Analyze Messages for HRI Content**

```bash
python hri_analyze_messages.py --start_date 2021-08 --end_date 2025-07 --extra_seeds "cobot,proxemics;shared-control"
```

**CLI arguments:**

| Argument               | Description                                                         |
| ---------------------- | ------------------------------------------------------------------- |
| `--start_date YYYY-MM` | Filter start month (default: 2021-08)                               |
| `--end_date YYYY-MM`   | Filter end month (default: 2025-07)                                 |
| `--extra_seeds`        | Extra keywords to treat as HRI-relevant (comma/semicolon-separated) |

You can now supply **extra keywords** at runtime via `--extra_seeds`. These are merged with the built-in `HRI_SEED_KEYWORDS` before filtering.

Example:

```bash
python hri_analyze_messages.py --extra_seeds "cobot, proxemics;shared-control"
```

---

### **Step 3: Upload Results to MongoDB Atlas (Optional)**

1. **Set up your MongoDB Atlas cluster:**

   * Go to [MongoDB Atlas](https://cloud.mongodb.com/).
   * Create a cluster (if you don’t already have one).
   * Create a database user with **read/write** permissions.
   * Whitelist your IP address in **Network Access**.
   * Copy your connection URI from **Clusters → Connect → Connect your application**.

2. **Run the upload script:**

```python
from pymongo.mongo_client import MongoClient
import urllib.parse
import pandas as pd

# Encode your password to avoid URI issues
password = urllib.parse.quote("YOUR_PASSWORD_HERE")

# Connection URI (replace placeholders)
uri = f"mongodb+srv://USERNAME:{password}@YOUR_CLUSTER.mongodb.net/?retryWrites=true&w=majority&appName=HMI"

# Connect to MongoDB
client = MongoClient(uri)
try:
    client.admin.command('ping')
    print("✅ Connected to MongoDB!")
except Exception as e:
    print("❌ Connection failed:", e)

# Load CSV and insert into MongoDB
df = pd.read_csv("hri_analysis_summary.csv")
collection = client["sympa_scraper"]["sympa_collection"]
collection.insert_many(df.to_dict("records"))

print(f"✅ Uploaded {len(df)} records to MongoDB!")
```

3. **View your data in Atlas:**

   * Log into [MongoDB Atlas](https://cloud.mongodb.com/).
   * Select your cluster → **Browse Collections**.
   * Choose `sympa_scraper` → `sympa_collection`.
   * View your uploaded CSV as JSON documents.

---

## 📊 Output: `hri_analysis_summary.csv`

| Column              | Description                                             |
| ------------------- | ------------------------------------------------------- |
| `url`               | Source message URL                                      |
| `sender_name`       | Parsed name of sender                                   |
| `sender_email`      | Email address of sender                                 |
| `institution`       | Inferred institution (based on email domain or content) |
| `subject`           | Cleaned subject line                                    |
| `hri_phrases_found` | Extracted HRI-relevant phrases                          |
| `people_found`      | Named persons identified in the message                 |
| `embedded_urls`     | Any URLs embedded in the message body                   |

---

## 🧠 Keyword Filtering

* Built-in HRI keyword list (`HRI_SEED_KEYWORDS`)
* Add extra runtime keywords via `--extra_seeds`
* Filters out noise with an extensive stopword list
* Uses spaCy NER + noun chunking for entity and phrase extraction

---

## ⚠️ Headless Mode Warning

The archive requires clicking an **"I'm not a spammer"** button.
This cannot be automated in headless mode.

Keep `headless=False` in both scripts:

```python
browser = await p.chromium.launch(headless=False)
```

---

## 🧪 Example Use Cases

* Identify researchers and labs working on HRI or other topics
* Track calls for papers & conference announcements
* Map institutions from email domains
* Store and query results in MongoDB Atlas

---

## 📌 Notes

* Never commit real MongoDB credentials to GitHub — use `.env` or environment variables for production.
* Some messages may be skipped due to malformed HTML.
* Gmail/Yahoo domains are matched to institutions via message text search.

---
