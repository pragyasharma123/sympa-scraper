# 🤖 sympa-scraper

This project automates the scraping, filtering, and keyword extraction of archived messages from the [Robotics-Worldwide mailing list](https://www.lists.kit.edu/sympa/arc/robotics-worldwide). It identifies messages related to Human-Robot Interaction (HRI) based on NLP and keyword matching, then saves structured outputs to CSV.

---

## 📂 Project Structure

| File                     | Purpose                                                                         |
| -------------------------| ------------------------------------------------------------------------------- |
| collect_all_messages.py  | Collects all individual message URLs from the archive                           |
| hri_analyze_messages.py  | Parses message HTML, extracts metadata, applies NLP, and outputs structured CSV |
| all_message_links.txt    | Output list of all message URLs from the archive                                |
| hri_analysis_summary.csv | Final analysis results: sender, subject, institution, keywords, etc.            |

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
* Bypasses any anti-spam button.
* Collects monthly archive URLs.
* Extracts individual message URLs.
* Saves them to `all_message_links.txt`.

### 2. **Step 2: Analyze Messages for HRI Content**

```bash
python hri_analyze_messages.py --start_date 2021-08 --end_date 2025-07
```

Optional CLI arguments:

* `--start_date YYYY-MM` — Filter start month (default: 2021-08)
* `--end_date YYYY-MM` — Filter end month (default: 2025-07)

This script:

* Loads URLs from `all_message_links.txt`
* Filters them by date
* Extracts metadata (sender, subject, domain, etc.)
* Parses HTML body using Playwright and BeautifulSoup
* Applies NLP using spaCy to:

  * Extract noun phrases
  * Identify HRI-related keywords
  * Detect sender names and email domains
* Saves output to `hri_analysis_summary.csv`

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

* Uses a predefined HRI keyword list (`HRI_SEED_KEYWORDS`)
* Filters out noise via extensive stopword list
* Extracts relevant noun phrases and people names using spaCy's NER and noun chunking

---

## 🧪 Example Use Cases

* Identify researchers and labs working on HRI topics
* Track conference announcements and calls for papers
* Map email domains to institutions for community analysis
* Build a database of people and topics from message history

---

## 📌 Notes

* Some messages may fail to parse due to malformed HTML or missing body content — these are skipped with error logs.
* Messages with domains like Gmail are heuristically assigned institutions using known affiliations mentioned in the body.

---

## 🤝 Acknowledgments

* Robotics-Worldwide mailing list ([KIT.edu](https://www.lists.kit.edu))
* `spaCy` for NLP
* `Playwright` for headless browser automation
* `BeautifulSoup` for HTML parsing

---

