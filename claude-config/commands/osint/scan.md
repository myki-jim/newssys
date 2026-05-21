Perform a quick reconnaissance scan on $ARGUMENTS:
1. Resolve to IP: `dig +short $ARGUMENTS`
2. Quick port scan: `nmap -F --open $ARGUMENTS`
3. If web ports open (80,443,8080,8443), grab headers: `curl -sI http://$ARGUMENTS`
4. WHOIS on the IP: `whois <ip>`
5. IP geolocation: `curl -s "http://ip-api.com/json/<ip>" | jq`

Report open ports, services, web technologies, and hosting info.
