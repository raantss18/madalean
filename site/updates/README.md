# Signed update channel (source directory)

The release process (scripts/sign_release.sh, ARCHITECTURE §16–17) puts `stable.json` and `stable.json.sig` here.
`site/build.py` verifies the signature against the public key embedded in `madalean/update_checkers/selfupdate.py`,
refuses to publish a manifest that does not verify, and copies both files byte for byte to `updates/` on the site.
Never edit `stable.json` by hand after signing (the signature covers its exact bytes). Format: docs/SITE.md §3.
