Run full DNS reconnaissance on $ARGUMENTS:
1. `dig $ARGUMENTS ANY +noall +answer` — all records
2. `dig $ARGUMENTS A AAAA MX NS TXT SOA CNAME +short` — key types
3. `dig _dmarc.$ARGUMENTS TXT +short` — DMARC
4. `dig TXT $ARGUMENTS | grep -i spf` — SPF
5. `dig -x` on any IPs found — reverse DNS
6. Check crt.sh for subdomains: `curl -s "https://crt.sh/?q=%25.$ARGUMENTS&output=json" | jq '.[].name_value' | sort -u | head -20`

Summarize all findings, note any security concerns (missing DMARC, etc.).
