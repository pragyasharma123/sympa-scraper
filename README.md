Here’s how I’d update your README so it matches your new code with the `--extra_seeds` CLI option and the merged HRI keyword handling.

---

# 🤖 sympa-scraper

This project automates the scraping, filtering, and keyword extraction of archived messages from the [Robotics-Worldwide mailing list](https://www.lists.kit.edu/sympa/arc/robotics-worldwide).
It identifies messages related to Human-Robot Interaction (HRI) based on NLP and keyword matching, with the option to **add custom keywords from the command line**.
The results are saved as a structured CSV file.

---

## 📂 Project Structure

| File                       | Purpose                                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `collect_all_messages.py`  | Collects all individual message URLs from the archive                                                        |
| `hri_analyze_messages.py`  | Parses message HTML, extracts metadata, applies NLP, filters using built-in and custom keywords, outputs CSV |
| `all_message_links.txt`    | List of all message URLs from the archive                                                                    |
| `hri_analysis_summary.csv` | Final analysis results: sender, subject, institution, keywords, etc.                                         |

---

## 🔧 Requirements

* Python 3.8+
* [Playwright](https://playwright.dev/python/)
* [spaCy](https://spacy.io/)
* BeautifulSoup (`bs4`)

Install dependencies:

```bash
pip install playwright bs4 spacy
python -m playwright install
python -m spacy download en_core_web_sm
```

---

## 🚀 Usage

### 1. **Step 1: Scrape All Message Links**

```bash
python collect_all_messages.py
```

* Opens the Robotics-Worldwide archive.
* Bypasses the anti-spam confirmation.
* Collects monthly archive URLs.
* Extracts individual message URLs.
* Saves them to `all_message_links.txt`.

---

### 2. **Step 2: Analyze Messages for HRI Content**

```bash
python hri_analyze_messages.py --start_date 2021-08 --end_date 2025-07 --extra_seeds "cobot,proxemics;shared-control"
```

**CLI arguments:**

| Argument               | Description                                                         |
| ---------------------- | ------------------------------------------------------------------- |
| `--start_date YYYY-MM` | Filter start month (default: 2021-08)                               |
| `--end_date YYYY-MM`   | Filter end month (default: 2025-07)                                 |
| `--extra_seeds`        | Extra keywords to treat as HRI-relevant (comma/semicolon-separated) |

**What’s new:**
You can now supply **extra HRI keywords** at runtime via `--extra_seeds`. These will be merged with the built-in `HRI_SEED_KEYWORDS` before filtering.

Example:

```bash
python hri_analyze_messages.py --extra_seeds "cobot, proxemics;shared-control"
```

This will match phrases containing *cobot*, *proxemics*, or *shared-control* in addition to the default seed list.

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

* Uses a built-in HRI keyword list (`HRI_SEED_KEYWORDS`)
* Optional: merge in extra runtime keywords via `--extra_seeds`
* Filters out noise using a large stopword list
* Extracts relevant noun phrases and people names using spaCy’s NER and noun chunking

---

## ⚠️ Important: Headless Mode Warning

The archive requires an **"I'm not a spammer"** confirmation click.
This cannot be automated in headless mode, so:

* **Keep `headless=False`** in both scripts
* Example (already in code):

```python
browser = await p.chromium.launch(headless=False)
```

---

## 🧪 Example Use Cases

* Identify researchers and labs working on HRI or custom topics
* Track conference announcements and calls for papers
* Map email domains to institutions for community analysis
* Build a keyword-based database of people and topics from mailing list archives

---

## 📌 Notes

* Some messages may fail to parse due to malformed HTML — these are logged and skipped.
* Generic domains (e.g., Gmail) are assigned institutions by searching for known affiliations in the message text.
* The new `--extra_seeds` option makes it easy to adapt the script for **other research areas**, not just HRI.

---

