---
name: recon-osint
description: >
  Use whenever the user asks for domain reconnaissance, WHOIS lookup, DNS enumeration,
  subdomain discovery, IP geolocation, port scanning, certificate transparency,
  email security (SPF/DKIM/DMARC), or OSINT gathering. Triggered by keywords:
  recon, osint, whois, dns, dig, nslookup, subdomain, enumerate, scan, footprint,
  fingerprint, email security, traceroute, cert transparency, crt.sh, open ports.
version: 1.0.0
allowed-tools: [Bash, WebFetch, WebSearch]
user-invocable: true
---

# Reconnaissance & OSINT

Use existing system tools (`whois`, `dig`, `nslookup`, `nmap`, `curl`, `traceroute`, `ping`) to perform reconnaissance. DO NOT install extra packages — use what's available.

## Core workflows

### WHOIS lookup
Use `whois <domain>` for registration data. Parse registrar, dates, nameservers. Use `whois <IP>` for IP range/ASN info.

### DNS enumeration
- `dig <domain> ANY` — all records
- `dig <domain> A/AAAA/MX/NS/TXT/SOA/CNAME` — specific types
- `dig axfr <domain> @<ns>` — zone transfer (rarely works but worth trying)
- `nslookup <domain>` — basic resolution
- Reverse DNS: `dig -x <IP>`

### Email security
- `dig <domain> TXT | grep spf` — SPF record
- `dig <domain> TXT | grep DMARC` or `dig _dmarc.<domain> TXT`
- Check DKIM selectors: `dig <selector>._domainkey.<domain> TXT`

### Certificate transparency
Use `curl -s "https://crt.sh/?q=%25.<domain>&output=json" | jq '.[].name_value' | sort -u`
to discover subdomains from CT logs.

### Subdomain enumeration
1. CT logs via crt.sh (passive)
2. DNS brute with common subdomains: `for sub in www mail admin api dev; do dig +short $sub.<domain>; done`
3. Check if subdomains resolve and are alive

### Port scanning
- Quick top ports: `nmap -F --open <target>`
- Full scan: `nmap -p- --open <target>`
- Service detection: `nmap -sV -sC <target>`
- Stealth: `nmap -sS -Pn <target>`

### IP geolocation
`curl -s "http://ip-api.com/json/<IP>" | jq`

### Technology fingerprinting
`curl -sI <url>` for HTTP headers (Server, X-Powered-By, etc.)

### Cross-reference with News System
Always check the internal news database for domain/IP mentions:
`curl -s "http://backend:8000/api/v1/articles?keyword=<domain>&page_size=20"`

## Output format
Always present findings as a structured report:
1. **Target**: domain/IP
2. **WHOIS**: registrar, dates, nameservers
3. **DNS**: key records found
4. **Subdomains**: discovered + sources
5. **Email security**: SPF/DKIM/DMARC status
6. **Ports**: open ports with services
7. **News mentions**: articles from news system mentioning this target
8. **Summary**: key risks and recommendations
