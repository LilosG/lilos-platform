# OAuth and Secret Boundary

Production secret storage is an infrastructure adapter. The relational database stores opaque references and non-secret expiry/health metadata only. OAuth callback processing validates tenant-bound hashed state, expiry, exact redirect URI, one-time consumption, PKCE, and provider errors before storing returned credentials through that adapter. Callbacks are generic on failure and never echo codes or tokens.
