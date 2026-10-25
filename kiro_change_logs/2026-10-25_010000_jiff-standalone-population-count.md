# Standalone JIFF population count

**Files changed:** `jiff/`, `.gitignore`.

Added an isolated two-party JIFF demo with separate researcher and registrar inputs and a localhost relay that serves only allowlisted assets. The protocol secret-shares categorical values and query-presence bits and opens only the aggregate count. The browser binds public schema and population dimensions into its session identifier and rejects unsupported inputs. Integration tests compare real MPC counts against a plaintext oracle for exact, generalized, zero-match and wildcard queries, and check output openings and static-file isolation. Documented the trusted-preprocessing assumption, metadata and exact-count leakage, prototype scale limits, and the remaining risk-engine integration work. The existing pandas scoring path and privacy gate are unchanged.
