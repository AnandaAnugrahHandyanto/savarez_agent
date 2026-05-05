"""Per-property agent loops.

Each loop is a small, file-driven runtime that exercises a subset of the
UCPM SOP procedures end-to-end without depending on Postgres, IMAP/SMTP,
or external services. Real I/O is wired in later.
"""
