# Pin Python 3.13 for hosted builds

**Files changed:**
- `.python-version` (new)

A new Render service built with its default Python 3.14, where pandas 2.2.3 has no prebuilt wheel, so the build tried to compile pandas from source and failed. Render reads `.python-version`, so builds now use Python 3.13.1 even when the PYTHON_VERSION environment variable is not set.
