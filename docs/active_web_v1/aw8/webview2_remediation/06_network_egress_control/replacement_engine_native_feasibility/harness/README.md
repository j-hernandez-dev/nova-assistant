# Native CEF feasibility harness — test-only

This directory is not a product engine, Application or adapter. It has no Nova imports. It consumes one exact official CEF minimal binary distribution; no evergreen runtime. Sources are versioned with the evidence; the vendor package lives in a separately owned private temporary harness root.

- `probe.cpp`: direct C API, ABI hash check, one OSR browser, explicit profile/resources, startup/stop events and scalar process receipts.
- `build.ps1`: existing MSVC + Windows SDK only; exact package SHA256; ICU deployment and x64 stack reserve. No installation or global setting change.
- `run_probe.py`: standard-library-only offline HTTP proxy/target/STUN fixture, calibrated UDP OWNER_PID, owned Job, one critical native run; no model authority.

The tested stock profile FAILED WebRTC suppression. Do not run more combinations or treat these scripts as a certified profile. Re-execution requires a separate human direction.

The failed preparatory initialize attempt is preserved; successful preparation is not WebRTC suppression. The final probe saw real secure-context RTC/ICE/STUN and stopped. Logs do not contain page DOM, ICE address strings, credentials, cookies or raw packet payloads.

Binary/runtime are retained as private harness artifacts. New profile deletion was tool-policy blocked and remains CLEANUP_UNCONFIRMED. No historical UDF cleanup is authorized by this harness.

Reproduction recipes, if separately authorized: obtain the exact package/hash in candidate_identity.json, extract without path traversal into an owned short private root; run build.ps1 with that root; run run_probe.py with that root. Do not use a product profile, modify policy, disable TLS validation or inject arbitrary JS. This text is documentation, not authorization for another execution.
