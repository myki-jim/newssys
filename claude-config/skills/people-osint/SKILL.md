---
name: people-osint
description: >
  Use whenever the user asks to find a person, investigate someone, look up
  email/phone/username, check social media profiles, search breach data,
  or gather intelligence about an individual. Triggered by keywords:
  find person, who is, investigate, email lookup, username search, social media,
  breach, dox, background check, profile, identity.
version: 1.0.0
allowed-tools: [Bash, WebFetch, WebSearch]
user-invocable: true
---

# People OSINT

Use system tools (`whois`, `dig`, `curl`, `nslookup`) plus web search. DO NOT install extra packages.

## Core Workflows

### 1. Email Investigation
- Check email format validity (basic regex)
- Search email in breach databases via web search: `site:haveibeenpwned.com OR site:dehashed.com "<email>"`
- Check if email has associated accounts: search `"<email>" site:github.com OR site:linkedin.com OR site:twitter.com OR site:facebook.com`
- Look up domain of email: `whois <domain>` and `dig <domain> MX`
- Check if email appears in paste sites: search `"<email>" site:pastebin.com OR site:justpaste.it`

### 2. Username Search
- Cross-platform username check:
  ```
  for platform in github twitter instagram reddit linkedin medium deviantart pinterest; do
    echo "=== $platform ==="
    curl -sI "https://$platform.com/<username>" | head -1
  done
  ```
- Web search for username across platforms
- Check username in known data breaches

### 3. Name Investigation
- Search full name with quotes: `"<full name>"` in web search
- Search name + location/context keywords
- Check news mentions in the internal news system:
  `curl -s "http://backend:8000/api/v1/articles?keyword=<name>&page_size=20&sort_by=publish_time&sort_order=desc"`
- Search name + "arrested" / "convicted" / "charged" / "lawsuit" / "filed"
- Search name + "linkedin" / "cv" / "resume" / "bio"
- For Chinese names: search on Baidu, check Weibo mentions

### 4. Phone Number Investigation
- Basic format validation by country code
- Web search: `"<phone>"` (with quotes)
- Check if linked to social accounts
- Search in news system articles: `curl -s "http://backend:8000/api/v1/articles?keyword=<phone>&page_size=10"`

### 5. Domain/Website Owner Investigation
- `whois <domain>` — registrant info, dates, nameservers
- `dig <domain> ANY` — DNS records
- Historical WHOIS: web search `<domain> whois history`
- Check crt.sh for SSL certificates: `curl -s "https://crt.sh/?q=%25.<domain>&output=json" | jq '.[].name_value' | sort -u`
- Check Wayback Machine: `curl -s "http://web.archive.org/cdx/search/cdx?url=*.domain.com&output=text&limit=10"`
- Search news system for domain mentions

### 6. Social Media Deep Dive
- Get public profile pages via curl
- Check follower counts, join dates, post frequency
- Extract mentioned locations, employers, associates
- Cross-reference with news system articles

### 7. Cross-Reference with News System
Always check the internal news database:
```
curl -s "http://backend:8000/api/v1/articles?keyword=<name/email/username>&page_size=20&sort_by=publish_time&sort_order=desc"
curl -s "http://backend:8000/api/v1/search?query=<name>&max_results=10"
```

## Output Format
Present findings as a structured dossier:
1. **Subject**: name/email/username investigated
2. **Identity Summary**: known names, aliases, locations
3. **Online Presence**: accounts found per platform, profile URLs, follower counts
4. **News Mentions**: relevant articles from news system, dates, summaries
5. **Domain/Email**: associated domains, email reputation
6. **Risk Indicators**: breach appearances, negative news, suspicious activity
7. **Sources**: all URLs and references

## Privacy & Ethics
- Only use PUBLICLY available information
- Do NOT attempt to access private accounts
- Do NOT use stolen/breached credentials
- Mark unverified information clearly
