Discover subdomains for $ARGUMENTS:
1. Certificate transparency (crt.sh): `curl -s "https://crt.sh/?q=%25.$ARGUMENTS&output=json" | jq -r '.[].name_value' | sort -u`
2. Common subdomain brute: for sub in www mail admin api dev portal vpn staging test blog cdn status remote secure; do dig +short $sub.$ARGUMENTS | grep -v '^$' && echo $sub.$ARGUMENTS; done
3. Verify which subdomains are alive: `for host in <subdomains>; do curl -sI -m 3 http://$host >/dev/null 2>&1 && echo "$host ALIVE"; done`
4. Check for wildcard DNS: `dig +short randomnonexistent12345.$ARGUMENTS` — if it resolves, wildcard is active

Report all discovered subdomains with live/dead status.
