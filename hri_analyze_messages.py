import asyncio
import csv
import re
from collections import Counter, defaultdict
from playwright.async_api import async_playwright
import string
import spacy
from bs4 import BeautifulSoup, NavigableString, Comment
import traceback # For detailed error logging if needed

# --- Command-Line Date Filtering Configuration ---
def get_date_args():
    import argparse
    from datetime import datetime

    def valid_yyyymm(s):
        try:
            dt = datetime.strptime(s, "%Y-%m")
            return dt.year, dt.month
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid date format: '{s}'. Use YYYY-MM (e.g., 2021-08)")

    parser = argparse.ArgumentParser(description="Filter mailing list URLs by date range.")
    parser.add_argument("--start_date", type=valid_yyyymm, default=(2021, 8),
                        help="Start date in YYYY-MM format (default: 2021-08)")
    parser.add_argument("--end_date", type=valid_yyyymm, default=(2025, 7),
                        help="End date in YYYY-MM format (default: 2025-07)")
    return parser.parse_args()



# --- NLP Setup ---
nlp = spacy.load("en_core_web_sm")

STOPWORDS = {
    "an", "the", "and", "for", "with", "that", "this", "from", "you", "have", "are", "will", "your", "has", "been", "also", "not", "all", "any", "can", "use", "andor", "our", "new", "who", "more", "their", "may", "but", "these", "other", "which", "they", "how", "what", "such", "some", "its", "now", "please", "if", "each", "get", "us", "see", "below", "about", "we", "one", "two", "paper", "submission", "deadline", "cfp", "call", "conference", "journal", "publication", "university", "department", "phd", "candidate", "student", "abstract", "doctoral", "researcher", "graduate", "postdoc", "postdoctoral", "fellowship", "scholarship", "studentship", "mresphd", "epsrc", "cdt", "workshop", "symposium", "meeting", "seminar", "presentation", "date", "event", "events", "session", "sessions", "special", "guest", "speaker", "speakers", "talk", "talks", "talking", "discussion", "discussions", "program", "schedule", "invitation", "announcement", "application", "position", "opportunity", "prof", "tenth", "eleventh", "twelfth", "semester", "long", "hour", "information", "website", "link", "page", "contact", "email", "message", "emailing", "reply", "replying", "respond", "responding", "replyto", "reply_to", "replies", "replied", "replied to", "apology", "posting", "attachment", "format", "review", "comment", "description", "details", "detail", "further", "follow", "area", "part", "aspect", "job", "engineer", "applicant", "successful", "direct", "supervision", "multiple", "background", "multidisciplinary", "team", "citizen", "citizenship", "visa", "individual", "emphasis", "highly", "strongly", "encourage", "encouraged", "encouraging", "available", "high", "quality", "high quality", "highly qualified", "highly motivated", "outstanding", "select", "many", "several", "hightech", "wellknown", "interesting", "exciting", "lineup", "funding", "funded", "funds", "fully", "fund", "defense", "change", "world", "national", "vision", "unique", "scientific", "context", "associate", "risk", "future", "infrastructure", "professional", "initiative", "theme", "tradition", "xheadbodysepend", "xmsgbodyend", "xheadofmessage", "xbodyofmessage", "xheadofmessageend", "xheadbodysepbegin", "meetingsseminar", "unknown", "subject", "ryerson", "uwmadison", "tokyo", "japan", "toronto", "canada", "nottingham", "wisconsin", "london", "uk", "iit", "genova", "italy", "notre", "dame", "bilge", "mutlu", "royal", "geographical", "society", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "next", "monthly", "every", "technology", "engineering", "software", "development", "company", "colleague", "registration", "dot", "project", "leadership", "view", "series", "wrss", "roboticsworldwide", "prefer", "worldwide", "international", "center", "centre", "main", "responsibility", "versatile", "crossdisciplinary", "skill", "complex", "challenge", "fee", "fullyfunded", "small", "number", "euinternational", "lab", "dept", "computer", "rcvlryersonca", "science", "group", "laboratory", "archive", "list", "corresponding", "electrical", "mechanical", "biomedical", "topic", "traditional", "note", "requirement", "professor", "research", "news", "content", "ieee", "summer", "school", "istituto", "italiano", "di", "tecnologia"
}
if "robotic" in STOPWORDS:
    STOPWORDS.remove("robotic")

# --- HRI Core Vocabulary for Final Filtering ---
HRI_SEED_KEYWORDS = {
    "roman","communication", "RO-MAN", "hri", "hci", "interaction", "interactive", "usability", "robot", "robotic", "robotics", "agent", "autonomous", "automation", "ai", "intelligence", "artificial", "manipulator", "actuator,", "computing", "emotion", "psychology", "cognitive", "cognition", "haptic", "tactile", "teleoperation", "telerobotic", "shared", "telepresence", "assistive", "wearable", "exoskeleton", "rehabilitation", "humanoid", "navigation", "localization", "slam", "mapping", "perception", "sensing", "sensor", "gesture", "gaze", "voice", "multimodal", "modality", "virtual", "augmented", "reality", "vr", "ar", "vrar", "dimension", "frontier", "technique", "physical", "detection", "integration", "locomotion", "posture"
}

# --- Lists for NER and Institution Inference ---
KNOWN_INSTITUTIONS = {
    "university of nottingham", "nottingham", "tokyo university of science", "tus", "ryerson university", 
    "toronto metropolitan university", "university of wisconsin", "uw madison", "imperial college", "imperial.ac.uk",
    "italian institute of technology", "iit", "genova", "university of cambridge", "cambridge",
    "university of notre dame", "notre dame", "tu berlin", "technical university of berlin",
    "northeastern university", "northeastern", "utoronto", "university of toronto"
}

ORG_LOCATION_KEYWORDS_FOR_PERSON_FILTER = {
    'university', 'institute', 'department', 'center', 'centre', 'group', 'street', 'road', 'avenue', 'inc', 'ltd', 'llc', 'corp', 'gmbh', 'ag', 'bv', 'foundation', 'society', 'agency', 'lab', 'studios', 'team', 'toronto', 'japan', 'canada', 'wisconsin', 'berlin', 'genova', 'london', 'boston', 'microsoft', 'google', 'amazon', 'samsung', 'elementai', 'gm', 'lg', 'com', 'www', 'http', 'https', '.org', '.edu', '.net', '@', 'roboticsworldwide', 'isb', 'ieee', 'acii', 'aamas', 'itsc', 'fibe', 'cdt', 'epsrc', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
}
PERSON_NER_ERROR_BLACKLIST = {"inperson andor", "et al", "technical group"}


# --- Helper Functions ---
def clean_text(text):
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_noun_phrases_and_people(text, min_words_in_phrase=2, min_letters_per_word=2):
    doc = nlp(text)
    valid_phrases, people = [], set()
    for chunk in doc.noun_chunks:
        lemmas = [token.lemma_ for token in chunk if token.lemma_ not in STOPWORDS and token.is_alpha and len(token.lemma_) >= min_letters_per_word]
        if len(lemmas) >= min_words_in_phrase:
            valid_phrases.append(" ".join(lemmas))
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            candidate = ent.text.strip()
            parts = candidate.split()
            if not (len(parts) >= 2 and 4 < len(candidate) < 70): continue
            if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž\s'.’-]+", candidate): continue
            lower_candidate = candidate.lower()
            if lower_candidate in STOPWORDS or lower_candidate in PERSON_NER_ERROR_BLACKLIST: continue
            if any(keyword in lower_candidate for keyword in ORG_LOCATION_KEYWORDS_FOR_PERSON_FILTER if len(parts) <= 3): continue
            people.add(candidate)
    return valid_phrases, list(people)

def filter_for_hri_relevance(phrases, seed_keywords):
    return [phrase for phrase in phrases if any(word in seed_keywords for word in phrase.split())]

def extract_urls_from_text(text):
    if not text: return []
    url_pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
    return list(set(url_pattern.findall(text)))

def get_institution(domain, text, known_institutions):
    generic_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "pm.me"}
    if domain not in generic_domains and domain != "unknown_domain":
        return domain
    lower_text = text.lower()
    for inst in known_institutions:
        if inst in lower_text:
            if any(alias in inst for alias in ["nottingham"]): return "nottingham.ac.uk"
            if any(alias in inst for alias in ["tus", "tokyo"]): return "rs.tus.ac.jp"
            if any(alias in inst for alias in ["ryerson", "toronto metropolitan"]): return "ryerson.ca"
            if any(alias in inst for alias in ["wisconsin", "wisc"]): return "wisc.edu"
            if any(alias in inst for alias in ["imperial"]): return "imperial.ac.uk"
            if any(alias in inst for alias in ["iit", "genova"]): return "iit.it"
            if any(alias in inst for alias in ["cambridge"]): return "cam.ac.uk"
            if any(alias in inst for alias in ["notre dame"]): return "nd.edu"
            if any(alias in inst for alias in ["tu berlin"]): return "tu-berlin.de"
            if any(alias in inst for alias in ["northeastern"]): return "northeastern.edu"
            if any(alias in inst for alias in ["utoronto"]): return "utoronto.ca"
            return inst 
    return domain

def extract_domain(email):
    if not isinstance(email, str) or '@' not in email: return "unknown_domain"
    return email.split('@')[-1].lower()

def extract_sender_info(raw_from_field_text):
    sender_name, sender_email = "Unknown Name", "unknown@unknown"
    if not isinstance(raw_from_field_text, str): return sender_name, sender_email
    match1 = re.match(r'^\s*"?([^<"]*)"?\s*<(\S+@\S+)>', raw_from_field_text)
    if match1:
        sender_name = match1.group(1).strip().strip('"') or "Unknown Name"
        sender_email = match1.group(2).strip().lower()
        return sender_name, sender_email
    match2 = re.match(r'^\s*(\S+@\S+)\s*\((.+)\)', raw_from_field_text)
    if match2:
        sender_email = match2.group(1).strip().lower()
        sender_name = match2.group(2).strip()
        return sender_name, sender_email
    email_match = re.search(r'(\S+@\S+)', raw_from_field_text)
    if email_match:
        sender_email = email_match.group(1).strip().lower()
        potential_name = raw_from_field_text[:email_match.start()].strip().strip('<"\'()')
        if potential_name: sender_name = potential_name
    return sender_name, sender_email

def extract_subject_fallback(raw_text_input):
    subject_text = "Unknown Subject"
    if not isinstance(raw_text_input, str): return subject_text
    if "\n" in raw_text_input or len(raw_text_input) > 300:
        lines = re.findall(r"(?i)^Subject:\s*(.*)", raw_text_input, re.MULTILINE)
        if lines: subject_text = lines[0].strip()
    else: subject_text = raw_text_input.strip()
    subject_text = re.sub(r"^\[.*?\]\s*", "", subject_text, flags=re.IGNORECASE).strip()
    subject_text = re.sub(r"^(Re|Fwd|Fw|RE|FWD|FW):\s*", "", subject_text, flags=re.IGNORECASE).strip()
    return subject_text or "Unknown Subject (empty after cleaning)"

def get_body_text_from_html(html_snippet):
    if not html_snippet: return ""
    soup = BeautifulSoup(html_snippet, "html.parser")
    for tag in soup(['script', 'style', 'noscript', 'meta', 'title', 'head', 'link', 'button', 'input', 'select', 'textarea', 'form', 'nav', 'footer', 'header', 'aside']):
        tag.decompose()
    return re.sub(r'\n\s*\n+', '\n\n', soup.get_text(separator='\n', strip=True)).strip()

# --- Main Execution Logic ---
async def main():
    args = get_date_args()
    START_YEAR, START_MONTH = args.start_date
    END_YEAR, END_MONTH = args.end_date


    try:
        with open("all_message_links.txt", "r") as f:
            all_urls_from_file = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: all_message_links.txt not found."); return
    if not all_urls_from_file:
        print("No URLs found in all_message_links.txt."); return

    # --- DATE FILTERING LOGIC USING ARGS ---
    print(f"Found {len(all_urls_from_file)} total URLs in the file.")
    print(f"Filtering for dates from {START_YEAR}-{START_MONTH:02d} to {END_YEAR}-{END_MONTH:02d}...")

    date_pattern = re.compile(r'/(\d{4})-(\d{2})/')
    urls = []
    start_date_int = START_YEAR * 100 + START_MONTH
    end_date_int = END_YEAR * 100 + END_MONTH

    for url in all_urls_from_file:
        match = date_pattern.search(url)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            url_date_int = year * 100 + month
            if start_date_int <= url_date_int <= end_date_int:
                urls.append(url)
    print(f"Found {len(urls)} URLs within the specified date range to process.")


    if not urls:
        print("No matching URLs found to process. Exiting.")
        return

    all_rows_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        page = await context.new_page()

        for url_idx, url in enumerate(urls):
            print(f"\n--- Processing URL {url_idx+1}/{len(urls)}: {url} ---")
            row_data = {"url": url, "sender_name": "Unknown Name", "sender_email": "unknown@unknown", "institution": "unknown_domain", "subject": "Unknown Subject", "hri_phrases_found": "", "people_found": "", "embedded_urls": ""}
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
                html_content = await page.content()
                if not html_content or len(html_content) < 1000: raise Exception("HTML content too short or empty")
                
                soup = BeautifulSoup(html_content, "html.parser")

                extracted_headers = {}
                header_ul = None
                start_comment = soup.find(string=lambda t: isinstance(t, Comment) and "X-Head-of-Message" in t and "End" not in t)
                if start_comment:
                    node = start_comment.find_next_sibling()
                    while node:
                        if isinstance(node, Comment) and "X-Head-of-Message-End" in node: break
                        if node.name == 'ul': header_ul = node; break
                        node = node.find_next_sibling()
                
                if header_ul:
                    for li in header_ul.find_all('li', recursive=False):
                        strong_tag = li.find('strong')
                        if strong_tag:
                            key = strong_tag.get_text(strip=True).rstrip(':').strip()
                            value_parts = list(e.strip() for e in strong_tag.next_siblings if isinstance(e, NavigableString) and e.strip()) + \
                                          list(e.get_text(separator=' ', strip=True) for e in strong_tag.next_siblings if e.name)
                            extracted_headers[key] = " ".join(filter(None, value_parts)).strip()
                    sender_name, sender_email = extract_sender_info(extracted_headers.get("From", ""))
                    subject = extract_subject_fallback(extracted_headers.get("Subject", "Unknown Subject"))
                    # --- Fallback: infer name from email if sender_name is still unknown ---
                    if sender_name in {"Unknown Name", "", None} and isinstance(sender_email, str) and "@" in sender_email:
                        local_part = sender_email.split("@", 1)[0]  # everything before the @
                        tokens = re.split(r"[.\-_]", local_part)
                        clean_tokens = [t for t in tokens if t.isalpha() and len(t) > 1]

                        # Avoid using names from mailing list aliases
                        LIST_ALIASES = {"roboticsworldwide", "hri-list", "mailinglist", "listserv", "mailer-daemon"}
                        if set(clean_tokens).isdisjoint(LIST_ALIASES) and clean_tokens:
                            sender_name = " ".join(token.capitalize() for token in clean_tokens)
                        else:
                           sender_name = "Unknown Name"
                else:
                    raw_text = soup.get_text('\n', strip=True)
                    sender_name, sender_email = extract_sender_info(raw_text)
                    subject = extract_subject_fallback(raw_text)
                
                domain = extract_domain(sender_email)
                
                separator_hr = header_ul.find_next_sibling('hr') if header_ul else None
                html_snippet = None
                if separator_hr:
                    parts = [str(curr) for curr in separator_hr.find_next_siblings() if not (isinstance(curr, Comment) and curr.string and curr.string.strip() == "X-MsgBody-End")]
                    if parts: html_snippet = "".join(parts)
                else:
                    body_tag = soup.find('body')
                    if body_tag: html_snippet = str(body_tag)
                
                body_text = get_body_text_from_html(html_snippet) if html_snippet else "(Body not parsed)"
                
                if body_text and not body_text.startswith("("):
                    full_text_for_inference = subject + " " + body_text
                    final_institution = get_institution(domain, full_text_for_inference, KNOWN_INSTITUTIONS)
                    extracted_urls = extract_urls_from_text(body_text)
                    
                    raw_combined = f"{subject} {body_text}".lower()
                    partially_cleaned = clean_text(raw_combined)
                    artifacts = ["xbodyofmessage", "xheadbodysepend", "xmsgbodyend", "xheadofmessage"]
                    text_after_artifacts = re.sub(r'\b(' + '|'.join(artifacts) + r')\b', ' ', partially_cleaned)
                    final_clean = clean_text(text_after_artifacts)
                    
                    all_phrases, people = extract_noun_phrases_and_people(final_clean, min_words_in_phrase=2)
                    hri_phrases = filter_for_hri_relevance(all_phrases, HRI_SEED_KEYWORDS)

                    row_data.update({
                        "sender_name": sender_name, "sender_email": sender_email, "institution": final_institution, "subject": subject,
                        "hri_phrases_found": "; ".join(sorted(list(set(hri_phrases)))),
                        "people_found": "; ".join(sorted(people)),
                        "embedded_urls": "; ".join(sorted(extracted_urls))
                    })
                    
                    print(f"  📨 Subject: {subject}")
                    print(f"  👤 Sender: {sender_name} <{sender_email}> (Final Institution: {final_institution})")
                    if hri_phrases: print(f"  💬 HRI Phrases (sample): {', '.join(hri_phrases[:3])}...")
                    if people: print(f"  👥 People (sample): {', '.join(sorted(people)[:3])}...")
                else:
                    # Still update the basic info even if body is not parsed for NLP
                    row_data.update({"sender_name": sender_name, "sender_email": sender_email, "institution": domain, "subject": subject})
            
            except Exception as e:
                print(f"  ⚠️ Processing Failed for {url}: {type(e).__name__} - {e}")
                traceback.print_exc()
                row_data.update({"subject": f"Processing Error ({type(e).__name__})"})

            all_rows_data.append(row_data)
        
        await context.close()
        await browser.close()

    # --- Saving Final Consolidated Output ---
    if all_rows_data:
        fieldnames = ["url", "sender_name", "sender_email", "institution", "subject", "hri_phrases_found", "people_found", "embedded_urls"]
        
        with open("hri_analysis_summary.csv", "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows_data)
        
        print("\n\n✅ Analysis complete. All data saved to hri_analysis_summary.csv")
    else:
        print("\n\n No data was processed to save.")


if __name__ == "__main__":
    asyncio.run(main())
