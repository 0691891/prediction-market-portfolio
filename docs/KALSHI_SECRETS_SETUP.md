# Kalshi credential setup (NO credentials stored in Git)

IMPORTANT: Replace the Kalshi API key pair that was pasted into chat before using it. Treat that private key as exposed. Revoke the old API key and create a new one in Kalshi. Do not commit either the API key ID or RSA private key to a source file, .env, dashboard JavaScript, GitHub Issue or Actions workflow.

Go to this repository > Settings > Secrets and variables > Actions > New repository secret. Add two secrets with newly generated values:

- KALSHI_API_KEY_ID: new Kalshi API key identifier.
- KALSHI_PRIVATE_KEY_PEM: complete newly generated multiline RSA private key including BEGIN/END lines.

Kalshi public market-data reads do not require these secrets; prefer unauthenticated endpoints for the read-only paper-pricing screen. Add authenticated client support only as a strictly read-only server-side service if portfolio/order access is later needed. NEVER allow the paper engine to place real orders.

Do not conflate ODDS_API_KEY (third-party sportsbook provider) with KALSHI_API_KEY_ID.

Streamlit Cloud secrets live separately in the Streamlit app Settings > Secrets if a server-side authenticated Kalshi client is implemented. Never embed secret values into a browser-served HTML artifact. The existing Kalshi integration is not validated as an authenticated account reader.
