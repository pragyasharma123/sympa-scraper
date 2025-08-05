import asyncio
import csv
import re
from playwright.async_api import async_playwright
import string
import spacy
from bs4 import BeautifulSoup, NavigableString, Comment
import traceback  # For detailed error logging if needed

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

    def csv_list(s: str):
        # Accept comma/semicolon separated; trim and drop empties
        parts = re.split(r"[;,]", s)
        return [p.strip() for p in parts if p.strip()]

    parser = argparse.ArgumentParser(description="Filter mailing list URLs by date range.")
    parser.add_argument("--start_date", type=valid_yyyymm, default=(2021, 8),
                        help="Start date in YYYY-MM format (default: 2021-08)")
    parser.add_argument("--end_date", type=valid_yyyymm, default=(2025, 7),
                        help="End date in YYYY-MM format (default: 2025-07)")
    parser.add_argument("--extra_seeds", type=csv_list, default=[],
                        help="Extra HRI seed keywords (comma/semicolon-separated). "
                             "Example: --extra_seeds 'cobot, proxemics;shared-control'")
    return parser.parse_args()

# --- NLP Setup ---
nlp = spacy.load("en_core_web_sm")

STOPWORDS = {
    "an","the","and","for","with","that","this","from","you","have","are","will","your","has","been",
    "also","not","all","any","can","use","andor","our","new","who","more","their","may","but","these",
    "other","which","they","how","what","such","some","its","now","please","if","each","get","us","see",
    "below","about","we","one","two","paper","submission","deadline","cfp","call","conference","journal",
    "publication","university","department","phd","candidate","student","abstract","doctoral","researcher",
    "graduate","postdoc","postdoctoral","fellowship","scholarship","studentship","mresphd","epsrc","cdt",
    "workshop","symposium","meeting","seminar","presentation","date","event","events","session","sessions",
    "special","guest","speaker","speakers","talk","talks","talking","discussion","discussions","program",
    "schedule","invitation","announcement","application","position","opportunity","prof","tenth","eleventh",
    "twelfth","semester","long","hour","information","website","link","page","contact","email","message",
    "emailing","reply","replying","respond","responding","replyto","reply_to","replies","replied","replied to",
    "apology","posting","attachment","format","review","comment","description","details","detail","further",
    "follow","area","part","aspect","job","engineer","applicant","successful","direct","supervision",
    "multiple","background","multidisciplinary","team","citizen","citizenship","visa","individual","emphasis",
    "highly","strongly","encourage","encouraged","encouraging","available","high","quality","high quality",
    "highly qualified","highly motivated","outstanding","select","many","several","hightech","wellknown",
    "interesting","exciting","lineup","funding","funded","funds","fully","fund","defense","change","world",
    "national","vision","unique","scientific","context","associate","risk","future","infrastructure",
    "professional","initiative","theme","tradition","xheadbodysepend","xmsgbodyend","xheadofmessage",
    "xbodyofmessage","xheadofmessageend","xheadbodysepbegin","meetingsseminar","unknown","subject","ryerson",
    "uwmadison","tokyo","japan","toronto","canada","nottingham","wisconsin","london","uk","iit","genova",
    "italy","notre","dame","bilge","mutlu","royal","geographical","society","january","february","march",
    "april","may","june","july","august","september","october","november","december","monday","tuesday",
    "wednesday","thursday","friday","saturday","sunday","next","monthly","every","technology","engineering",
    "software","development","company","colleague","registration","dot","project","leadership","view",
    "series","wrss","roboticsworldwide","prefer","worldwide","international","center","centre","main",
    "responsibility","versatile","crossdisciplinary","skill","complex","challenge","fee","fullyfunded","small",
    "number","euinternational","lab","dept","computer","rcvlryersonca","science","group","laboratory","archive",
    "list","corresponding","electrical","mechanical","biomedical","topic","traditional","note","requirement",
    "professor","research","news","content","ieee","summer","school","istituto","italiano","di","tecnologia"
}
if "robotic" in STOPWORDS:
    STOPWORDS.remove("robotic")

# --- HRI Core Vocabulary for Final Filtering ---
HRI_SEED_KEYWORDS = {
    "roman","communication","RO-MAN","hri","hci","interaction","interactive","usability","robot","robotic",
    "robotics","agent","autonomous","automation","ai","intelligence","artificial","manipulator","actuator,",
    "computing","emotion","psychology","cognitive","cognition","haptic","tactile","teleoperation","telerobotic",
    "shared","telepresence","assistive","wearable","exoskeleton","rehabilitation","humanoid","navigation",
    "localization","slam","mapping","perception","sensing","sensor","gesture","gaze","voice","multimodal",
    "modality","virtual","augmented","reality","vr","ar","vrar","dimension","frontier","technique","physical",
    "detection","integration","locomotion","posture"
}

# --- Lists for NER and Institution Inference ---
KNOWN_INSTITUTIONS = {
    "university of nottingham","nottingham","tokyo university of science","tus","ryerson university",
    "toronto metropolitan university","university of wisconsin","uw madison","imperial college","imperial.ac.uk",
    "italian institute of technology","iit","genova","university of cambridge","cambridge",
    "university of notre dame","notre dame","tu berlin","technical university of berlin",
    "northeastern university","northeastern","utoronto","university of toronto"
}

ORG_LOCATION_KEYWORDS_FOR_PERSON_FILTER = {
    'university','institute','department','center','centre','group','street','road','avenue','inc','ltd',
    'llc','corp','gmbh','ag','bv','foundation','society','agency','lab','studios','team','toronto','japan',
    'canada','wisconsin','berlin','genova','london','boston','microsoft','google','amazon','samsung',
    'elementai','gm','lg','com','www','http','https','.org','.edu','.net','@','roboticsworldwide','isb',
    'ieee','acii','aamas','itsc','fibe','cdt','epsrc','january','february','march','april','may','june',
    'july','august','september','october','november','december','monday','tuesday','wednesday','thursday',
    'friday','saturday','sunday'
}
PERSON_NER_ERROR_BLACKLIST = {"inperson andor","et al","technical group"}

# Tokens that suggest the "name" is actually an email/domain mashup or header junk
NAME_BAD_SUBSTRINGS = {
    "header","footer","unsubscribe","@",".edu",".ac.",".com",".org",".net","sutdedusg","unigeit","learningj"
}
# Reject tokens that look like glued email/domain fragments
DOMAINY_TOKEN = re.compile(r'(edu|ac|gov|org|com|net)[a-z]{0,3}$')

# --- URL/email cleaning for NER (case-preserving) ---
URL_RE   = re.compile(r'https?://\S+|www\.\S+')
EMAIL_RE = re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b')

def text_for_ner(subject: str, body: str) -> str:
    t = f"{subject}\n{body}"
    t = URL_RE.sub(" ", t)
    t = EMAIL_RE.sub(" ", t)
    return re.sub(r'\s+', ' ', t).strip()

# --- Sender inclusion helpers ---
SENDER_BAD_ALIASES = {"roboticsworldwide","daemon","mailer","listserv","postmaster","admin","noreply","no-reply"}

def looks_like_single_token_name(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž'.’-]{2,25}", token))

def include_sender(people_list, sender_name):
    s = re.sub(r"\s+", " ", (sender_name or "").strip('"\':<> ')).strip()
    if not s or s.lower() in SENDER_BAD_ALIASES:
        return people_list
    parts = s.split()
    if len(parts) == 1 and not looks_like_single_token_name(parts[0]):
        return people_list
    merged = list(set(people_list + [s]))
    return merged

# --- Person cleanup helpers (titles, capitalization guards) ---
TITLE_PREFIXES = {"prof","prof.","dr","dr.","mr","mr.","ms","ms.","mrs","mrs.","sir","madam","mx","mx."}
LOWER_PARTICLES = {"de","da","del","van","von","di","la","le","du","dos","das","bin","al","ibn","mac","mc","der"}

def strip_leading_titles(name: str) -> str:
    parts = name.strip().split()
    while parts and parts[0].lower().strip(".") in {t.strip(".") for t in TITLE_PREFIXES}:
        parts = parts[1:]
    return " ".join(parts)

def capitalized_name_pattern(name: str) -> bool:
    """Require at least two tokens that begin uppercase, allowing lowercase particles in between."""
    tokens = name.split()
    cap_count = 0
    for tok in tokens:
        if not tok:
            continue
        if tok[0].isupper():
            cap_count += 1
        elif tok.lower() in LOWER_PARTICLES:
            continue
        else:
            return False
    return cap_count >= 2

# Hard denylists for 'people'
PEOPLE_PHRASE_DENY_REGEX = re.compile(
    r"\b(curriculum\s+vitae|curriculum|vitae|resume|best\s+regards|kind\s+regards|warm\s+regards|"
    r"many\s+thanks|thank\s+you|thanks|cheers|dear\s+all|dear\s+colleagues|unsubscribe)\b",
    re.I
)
PEOPLE_TOKEN_DENY = {"curriculum","vitae","resume","regards","thanks","thank","dear","unsubscribe","signature","sig"}

def _normalize_simple(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s'-]+", " ", s)).strip().lower()

# --- Helper Functions (people) ---
def is_clean_name(name: str) -> bool:
    if not name or any(ch.isdigit() for ch in name):
        return False
    name = strip_leading_titles(name).strip()
    if not name:
        return False
    if PEOPLE_PHRASE_DENY_REGEX.search(name) or PEOPLE_PHRASE_DENY_REGEX.search(_normalize_simple(name)):
        return False
    parts = name.split()
    if any(p.lower() in PEOPLE_TOKEN_DENY for p in parts):
        return False
    if not (2 <= len(parts) <= 5):
        return False
    if not capitalized_name_pattern(name):
        return False
    if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž\s'.’-]+", name):
        return False
    if any(bad in name.lower() for bad in NAME_BAD_SUBSTRINGS):
        return False
    if any(DOMAINY_TOKEN.search(tok.lower()) for tok in parts):
        return False
    vowel_tokens = sum(1 for tok in parts if re.search(r"[aeiouAEIOU]", tok))
    return vowel_tokens >= 2

def post_filter_people(people):
    cleaned, seen = [], set()
    for p in people:
        if not isinstance(p, str):
            continue
        if '@' in p or any(ch.isdigit() for ch in p):
            continue
        if PEOPLE_PHRASE_DENY_REGEX.search(p) or PEOPLE_PHRASE_DENY_REGEX.search(_normalize_simple(p)):
            continue
        candidate = strip_leading_titles(p).strip()
        if not candidate:
            continue
        if 2 <= len(candidate.split()) <= 5 and all(2 <= len(tok) <= 25 for tok in candidate.split()):
            if not re.search(r'from.*@|header|footer|list|unsubscribe', candidate.lower()):
                if is_clean_name(candidate) and candidate not in seen:
                    seen.add(candidate)
                    cleaned.append(candidate)
    return cleaned

def clean_text(text):
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_sympa_body(soup: BeautifulSoup) -> str:
    """
    Prefer the Sympa body block between <!--X-Body-of-Message--> and <!--X-Body-of-Message-End-->.
    Fallbacks: header <hr> separator, or <body>.
    """
    # 1) Exact Sympa body block
    start = soup.find(string=lambda t: isinstance(t, Comment) and "X-Body-of-Message" in t and "End" not in t)
    if start:
        parts = []
        node = start.next_sibling
        while node:
            if isinstance(node, Comment) and "X-Body-of-Message-End" in node:
                break
            parts.append(str(node))
            node = node.next_sibling
        if parts:
            return "".join(parts)

    # 2) Try the <hr> after header <ul>
    header_start = soup.find(string=lambda t: isinstance(t, Comment) and "X-Head-of-Message" in t and "End" not in t)
    header_ul = None
    if header_start:
        node = header_start.next_sibling
        while node:
            if isinstance(node, Comment) and "X-Head-of-Message-End" in node:
                break
            if getattr(node, "name", None) == "ul":
                header_ul = node
                break
            node = node.next_sibling

    if header_ul:
        hr = header_ul.find_next_sibling("hr")
        if hr:
            parts = []
            node = hr.next_sibling
            while node:
                if isinstance(node, Comment) and ("X-Body-of-Message-End" in node or "X-MsgBody-End" in node):
                    break
                parts.append(str(node))
                node = node.next_sibling
            if parts:
                return "".join(parts)

    # 3) Fallback to <body>
    body_tag = soup.find("body")
    return str(body_tag) if body_tag else ""

# put once at module level for efficiency
SEED_SINGLETONS = {w.lower() for w in HRI_SEED_KEYWORDS}

def extract_noun_phrases_and_people(text_for_phrases: str, text_for_ner_input: str,
                                    min_words_in_phrase=2, min_letters_per_word=2):
    doc_phr = nlp(text_for_phrases)
    doc_ner = nlp(text_for_ner_input)

    valid_phrases, people = [], set()

    # --- HRI phrases ---
    for chunk in doc_phr.noun_chunks:
        lemmas = [tok.lemma_ for tok in chunk
                  if tok.lemma_ not in STOPWORDS and tok.is_alpha and len(tok.lemma_) >= min_letters_per_word]
        if len(lemmas) >= min_words_in_phrase:
            valid_phrases.append(" ".join(lemmas))
        elif len(lemmas) == 1 and lemmas[0].lower() in SEED_SINGLETONS:
            valid_phrases.append(lemmas[0])

    # de-dupe, preserve order
    seen = set()
    valid_phrases = [p for p in valid_phrases if not (p in seen or seen.add(p))]

    # --- PERSON NER ---
    for ent in doc_ner.ents:
        if ent.label_ != "PERSON":
            continue
        candidate = ent.text.strip().strip('"<>:')
        if '@' in candidate or len(candidate) < 2:
            continue
        candidate = strip_leading_titles(candidate)
        if not candidate:
            continue
        parts = candidate.split()
        if not (2 <= len(parts) <= 5 and len(candidate) < 80):
            continue
        if not capitalized_name_pattern(candidate):
            continue
        if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž\s'.’-]+", candidate):
            continue
        lower_candidate = candidate.lower()
        if lower_candidate in STOPWORDS or lower_candidate in PERSON_NER_ERROR_BLACKLIST:
            continue
        if len(parts) <= 2 and any(kw in lower_candidate for kw in ORG_LOCATION_KEYWORDS_FOR_PERSON_FILTER):
            continue
        people.add(candidate)

    filtered = post_filter_people(list(people))
    cleaned = [p for p in filtered if is_clean_name(p)]
    return valid_phrases, cleaned

# --- HRI relevance with normalized seed matching & stronger guards ---
_PUNC_TBL = str.maketrans("", "", string.punctuation)

def _normalize_token(tok: str) -> str:
    return tok.translate(_PUNC_TBL).lower()

HRI_SEED_NORMALIZED = {_normalize_token(w) for w in HRI_SEED_KEYWORDS if _normalize_token(w)}

# Require at least one *strong* HRI token by prefix
STRONG_HRI_PREFIXES = (
    "robot", "hri", "hci", "humanoid", "haptic", "teleop", "telerobot",
    "gesture", "gaze", "exoskeleton", "assistive", "rehabilitation",
    "autonom", "manipulat", "locomot", "perception", "sensing", "sensor",
    "slam", "localization", "mapping", "telepresence"
)

HRI_PHRASE_DENY_TOKENS = {
    "university","department","deadline","application","position","session","meeting","seminar",
    "speaker","talk","workshop","symposium","registration","conference","journal","cfp",
    "thanks","thank","regards","best","sincerely","please","dear","unsubscribe","subject","zoom","link"
}
HRI_ADMIN_REGEX = re.compile(
    r"\b(deadline|cfp|registration|register|workshop|symposium|seminar|meeting|session|speaker|talk|"
    r"journal|conference|unsubscribe|zoom|link)\b", re.I
)

def _has_strong_hri_token(tokens_norm):
    for t in tokens_norm:
        for pref in STRONG_HRI_PREFIXES:
            if t.startswith(pref):
                return True
    return False

def filter_for_hri_relevance(phrases, seed_keywords_normalized=HRI_SEED_NORMALIZED):
    kept = []
    for phrase in phrases:
        raw_tokens = phrase.split()
        toks_norm = [_normalize_token(t) for t in raw_tokens if t]
        toks_set = set(toks_norm)
        if not toks_set:
            continue

        # single-token allowance
        if len(toks_norm) == 1:
            t = toks_norm[0]
            if (t in seed_keywords_normalized) or _has_strong_hri_token([t]):
                kept.append(phrase)
            continue

        # multi-token logic
        if not (toks_set & seed_keywords_normalized):
            continue
        if not _has_strong_hri_token(toks_norm):
            continue
        if toks_set & HRI_PHRASE_DENY_TOKENS:
            continue
        if HRI_ADMIN_REGEX.search(" ".join(toks_norm)):
            continue
        if not (2 <= len(toks_norm) <= 8):
            continue
        if not any(len(t) >= 4 for t in toks_norm):
            continue
        sw_ratio = sum(1 for t in raw_tokens if t.lower() in STOPWORDS) / max(1, len(raw_tokens))
        if sw_ratio > 0.5:
            continue

        kept.append(phrase)

    # de-dupe, preserve order
    seen, out = set(), []
    for p in kept:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out

# --- URL extraction from HTML (anchors + bare links) ---
def extract_urls_from_html(html_snippet):
    if not html_snippet:
        return []
    soup = BeautifulSoup(html_snippet, "html.parser")
    urls = set()

    # hrefs from anchors
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("mailto:"):
            continue
        urls.add(href)

    # also catch bare URLs in visible text
    text = soup.get_text(" ", strip=True)
    url_pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
    urls.update(url_pattern.findall(text))

    return sorted(urls)

def get_institution(domain, text, known_institutions):
    generic_domains = {"gmail.com","yahoo.com","hotmail.com","outlook.com","aol.com","pm.me"}
    if domain not in generic_domains and domain != "unknown_domain":
        return domain
    lower_text = text.lower()
    for inst in known_institutions:
        if inst in lower_text:
            if any(alias in inst for alias in ["nottingham"]): return "nottingham.ac.uk"
            if any(alias in inst for alias in ["tus","tokyo"]): return "rs.tus.ac.jp"
            if any(alias in inst for alias in ["ryerson","toronto metropolitan"]): return "ryerson.ca"
            if any(alias in inst for alias in ["wisconsin","wisc"]): return "wisc.edu"
            if any(alias in inst for alias in ["imperial"]): return "imperial.ac.uk"
            if any(alias in inst for alias in ["iit","genova"]): return "iit.it"
            if any(alias in inst for alias in ["cambridge"]): return "cam.ac.uk"
            if any(alias in inst for alias in ["notre dame"]): return "nd.edu"
            if any(alias in inst for alias in ["tu berlin"]): return "tu-berlin.de"
            if any(alias in inst for alias in ["northeastern"]): return "northeastern.edu"
            if any(alias in inst for alias in ["utoronto"]): return "utoronto.ca"
            return inst
    return domain

def extract_domain(email):
    if not isinstance(email, str) or '@' not in email:
        return "unknown_domain"
    return email.split('@')[-1].lower()

def extract_sender_info(raw_from_field_text):
    sender_name, sender_email = "Unknown Name", "unknown@unknown"
    if not isinstance(raw_from_field_text, str):
        return sender_name, sender_email

    raw_from_field_text = raw_from_field_text.strip().strip('<>"')

    # Name <email@dom>
    match1 = re.match(r'^\s*"?([^<"]*)"?\s*<([^<>\s]+@[^<>\s]+)>', raw_from_field_text)
    if match1:
        sender_name = (match1.group(1) or "").strip().strip('"<>:') or "Unknown Name"
        sender_email = match1.group(2).strip().lower().strip('<>')
        return sender_name, sender_email

    # email@dom (Name)
    match2 = re.match(r'^\s*([^<>\s]+@[^<>\s]+)\s*\(([^)]+)\)', raw_from_field_text)
    if match2:
        sender_email = match2.group(1).strip().lower().strip('<>')
        sender_name = match2.group(2).strip().strip('"<>:')
        return sender_name, sender_email

    # Fallback: find any email; everything before email becomes name (if sane)
    email_match = re.search(r'([^<>\s]+@[^<>\s]+)', raw_from_field_text)
    if email_match:
        sender_email = email_match.group(1).strip().lower().strip('<>')
        potential_name = raw_from_field_text[:email_match.start()].strip().strip('<"\'():>')
        if potential_name and not any(alias in potential_name.lower() for alias in ["roboticsworldwide","daemon"]):
            sender_name = potential_name.strip('"<>:')
    return sender_name, sender_email

def extract_subject_fallback(raw_text_input):
    subject_text = "Unknown Subject"
    if not isinstance(raw_text_input, str):
        return subject_text

    if "\n" in raw_text_input or len(raw_text_input) > 300:
        lines = re.findall(r"(?i)^Subject:\s*(.*)", raw_text_input, re.MULTILINE)
        if lines:
            subject_text = lines[0].strip()
    else:
        subject_text = raw_text_input.strip()

    subject_text = re.sub(r"^\[.*?\]\s*", "", subject_text, flags=re.IGNORECASE)
    subject_text = re.sub(r"^(Re|Fwd|Fw|RE|FWD|FW):\s*", "", subject_text, flags=re.IGNORECASE)
    subject_text = subject_text.strip(" :")
    return subject_text or "Unknown Subject (empty after cleaning)"

def get_body_text_from_html(html_snippet):
    if not html_snippet:
        return ""
    soup = BeautifulSoup(html_snippet, "html.parser")
    for tag in soup(['script','style','noscript','meta','title','head','link',
                     'button','input','select','textarea','form','nav','footer','header','aside']):
        tag.decompose()
    return re.sub(r'\n\s*\n+', '\n\n', soup.get_text(separator='\n', strip=True)).strip()

# --- Main Execution Logic ---
async def main():
    args = get_date_args()
    START_YEAR, START_MONTH = args.start_date
    END_YEAR, END_MONTH = args.end_date

    # Build the combined seed set (built-in + CLI)
    extra_seeds_raw = set(args.extra_seeds or [])
    combined_seeds = set(HRI_SEED_KEYWORDS) | extra_seeds_raw
    HRI_SEED_NORMALIZED_LOCAL = {_normalize_token(w) for w in combined_seeds if _normalize_token(w)}

    if extra_seeds_raw:
        print(f"Using extra HRI seeds: {sorted(extra_seeds_raw)}")

    try:
        with open("all_message_links.txt", "r") as f:
            all_urls_from_file = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: all_message_links.txt not found."); return
    if not all_urls_from_file:
        print("No URLs found in all_message_links.txt."); return

    print(f"Found {len(all_urls_from_file)} total URLs in the file.")
    print(f"Filtering for dates from {START_YEAR}-{START_MONTH:02d} to {END_YEAR}-{END_MONTH:02d}...")

    urls = []
    start_date_int = START_YEAR * 100 + START_MONTH
    end_date_int   = END_YEAR   * 100 + END_MONTH

    for url in all_urls_from_file:
        match = re.search(r'/(\d{4})-(\d{2})/', url)
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
        context = await browser.new_context(user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                        "Chrome/91.0.4472.124 Safari/537.36"))
        page = await context.new_page()

        for url_idx, url in enumerate(urls):
            print(f"\n--- Processing URL {url_idx+1}/{len(urls)}: {url} ---")
            row_data = {
                "url": url, "sender_name": "Unknown Name", "sender_email": "unknown@unknown",
                "institution": "unknown_domain", "subject": "Unknown Subject",
                "hri_phrases_found": "", "people_found": "", "embedded_urls": ""
            }
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
                html_content = await page.content()
                if not html_content or len(html_content) < 1000:
                    raise Exception("HTML content too short or empty")

                soup = BeautifulSoup(html_content, "html.parser")

                # Extract headers (From/Subject) from header block if present
                extracted_headers = {}
                header_ul = None
                start_comment = soup.find(string=lambda t: isinstance(t, Comment) and "X-Head-of-Message" in t and "End" not in t)
                if start_comment:
                    node = start_comment.find_next_sibling()
                    while node:
                        if isinstance(node, Comment) and "X-Head-of-Message-End" in node:
                            break
                        if getattr(node, "name", None) == 'ul':
                            header_ul = node
                            break
                        node = node.find_next_sibling()

                if header_ul:
                    for li in header_ul.find_all('li', recursive=False):
                        strong_tag = li.find('strong')
                        if strong_tag:
                            key = strong_tag.get_text(strip=True).rstrip(':').strip()
                            value_parts = list(e.strip() for e in strong_tag.next_siblings
                                               if isinstance(e, NavigableString) and e.strip()) + \
                                          list(e.get_text(separator=' ', strip=True) for e in strong_tag.next_siblings if getattr(e, "name", None))
                            extracted_headers[key] = " ".join(filter(None, value_parts)).strip()
                    sender_name, sender_email = extract_sender_info(extracted_headers.get("From", ""))
                    subject = extract_subject_fallback(extracted_headers.get("Subject", "Unknown Subject"))
                    if sender_name in {"Unknown Name", "", None} and isinstance(sender_email, str) and "@" in sender_email:
                        local_part = sender_email.split("@", 1)[0]
                        tokens = re.split(r"[.\-_]", local_part)
                        clean_tokens = [t for t in tokens if t.isalpha() and len(t) > 1]
                        LIST_ALIASES = {"roboticsworldwide","hri-list","mailinglist","listserv","mailer-daemon"}
                        if set(clean_tokens).isdisjoint(LIST_ALIASES) and clean_tokens:
                            sender_name = " ".join(token.capitalize() for token in clean_tokens)
                        else:
                            sender_name = "Unknown Name"
                else:
                    raw_text = soup.get_text('\n', strip=True)
                    sender_name, sender_email = extract_sender_info(raw_text)
                    subject = extract_subject_fallback(raw_text)

                domain = extract_domain(sender_email)

                # Sympa body extraction
                html_snippet = extract_sympa_body(soup)
                body_text = get_body_text_from_html(html_snippet) if html_snippet else "(Body not parsed)"

                if body_text and not body_text.startswith("("):
                    # Build two variants of the text:
                    ner_text = text_for_ner(subject, body_text)                 # case-preserving for NER
                    phrases_text = clean_text(body_text.lower())                 # EXCLUDE subject from phrases
                    artifacts = ["xbodyofmessage","xheadbodysepend","xbodyofmessageend",
                                 "xmsgbodyend","xheadofmessage","xheadofmessageend"]
                    phrases_text = re.sub(r'\b(' + '|'.join(artifacts) + r')\b', ' ', phrases_text)
                    phrases_text = clean_text(phrases_text)

                    all_phrases, people = extract_noun_phrases_and_people(
                        text_for_phrases=phrases_text,
                        text_for_ner_input=ner_text,
                        min_words_in_phrase=2
                    )

                    # Add sender (with one-token exception if name-like), then re-filter/dedupe
                    people = include_sender(people, sender_name)
                    people = post_filter_people(people)
                    people = [p for p in people if is_clean_name(p)]

                    # Final guard: ensure sender appears if it looks like a real name
                    sn = strip_leading_titles((sender_name or "").strip('"\':<> ').strip())
                    if sn and sn != "Unknown Name" and is_clean_name(sn):
                        people = sorted(set(people + [sn]))

                    # Final cleanup
                    people = [p for p in people
                              if not PEOPLE_PHRASE_DENY_REGEX.search(p)
                              and not PEOPLE_PHRASE_DENY_REGEX.search(_normalize_simple(p))
                              and not all(tok.lower() in PEOPLE_TOKEN_DENY for tok in p.split())]

                    # --- HRI phrases with fallbacks ---
                    hri_phrases = filter_for_hri_relevance(
                        all_phrases,
                        seed_keywords_normalized=HRI_SEED_NORMALIZED_LOCAL
                    )

                    # Fallback 1: include subject if none found
                    if not hri_phrases:
                        phrases_text_with_subject = clean_text((subject + " " + body_text).lower())
                        phrases_text_with_subject = re.sub(r'\b(' + '|'.join(artifacts) + r')\b', ' ', phrases_text_with_subject)
                        phrases_text_with_subject = clean_text(phrases_text_with_subject)
                        all_phrases2, _ = extract_noun_phrases_and_people(
                            text_for_phrases=phrases_text_with_subject,
                            text_for_ner_input=ner_text,
                            min_words_in_phrase=2
                        )
                        hri_phrases = filter_for_hri_relevance(
                            all_phrases2,
                            seed_keywords_normalized=HRI_SEED_NORMALIZED_LOCAL
                        )

                    # Fallback 2: last-resort seed singleton sweep across subject+body
                    if not hri_phrases:
                        text_norm = (subject + " " + body_text).translate(str.maketrans("", "", string.punctuation)).lower()
                        seed_hits = sorted({
                            s for s in HRI_SEED_NORMALIZED_LOCAL
                            if re.search(r"\b" + re.escape(s) + r"\b", text_norm)
                        })
                        strong_hits = [s for s in seed_hits if _has_strong_hri_token([s])]
                        hri_phrases = strong_hits or seed_hits

                    final_institution = get_institution(domain, subject + " " + body_text, KNOWN_INSTITUTIONS)

                    # Extract URLs from HTML (not just text)
                    extracted_urls = extract_urls_from_html(html_snippet)

                    row_data.update({
                        "sender_name": sender_name,
                        "sender_email": sender_email,
                        "institution": final_institution,
                        "subject": subject,
                        "hri_phrases_found": "; ".join(sorted(set(hri_phrases))),
                        "people_found": "; ".join(sorted(set(people))),
                        "embedded_urls": "; ".join(sorted(extracted_urls))
                    })

                    print(f"  📨 Subject: {subject}")
                    print(f"  👤 Sender: {sender_name} <{sender_email}> (Final Institution: {final_institution})")
                    if hri_phrases:
                        print(f"  💬 HRI Phrases (sample): {', '.join(hri_phrases[:3])}...")
                    if people:
                        print(f"  👥 People (sample): {', '.join(sorted(people)[:3])}...")
                else:
                    row_data.update({
                        "sender_name": sender_name,
                        "sender_email": sender_email,
                        "institution": domain,
                        "subject": subject
                    })

            except Exception as e:
                print(f"  ⚠️ Processing Failed for {url}: {type(e).__name__} - {e}")
                traceback.print_exc()
                row_data.update({"subject": f"Processing Error ({type(e).__name__})"})

            all_rows_data.append(row_data)

        await context.close()
        await browser.close()

    # --- Saving Final Consolidated Output ---
    if all_rows_data:
        fieldnames = ["url","sender_name","sender_email","institution","subject",
                      "hri_phrases_found","people_found","embedded_urls"]

        # Coerce None -> ""
        for row in all_rows_data:
            for k in fieldnames:
                if row.get(k) is None:
                    row[k] = ""

        with open("hri_analysis_summary.csv", "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows_data)

        print("\n\n✅ Analysis complete. All data saved to hri_analysis_summary.csv")
    else:
        print("\n\n No data was processed to save.")

if __name__ == "__main__":
    asyncio.run(main())
