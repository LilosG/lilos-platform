# URL Normalization

Only HTTP(S) URLs without embedded credentials are accepted. Scheme and IDNA host are lowercased; default ports and fragments are removed; paths receive stable percent encoding. `www` and apex, path case, trailing slash, and query parameters remain distinct unless observed canonical or redirect evidence links them. Every alias retains its observed value and normalization reasons.
