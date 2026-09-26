# Source document inbox

Put your source PDFs, TXT/Markdown, DOCX, CSV, XLSX, JSON, or validated `*.pack.json`
domain packages here. This README is ignored by ingestion.

The app scans this directory at startup and before an estimate starts. A SHA-256
digest of file bytes **and metadata** identifies its version. Unchanged files are
skipped; new or changed files are extracted, snapshotted, chunked and indexed.
Earlier versions stay available for estimates that already reference them.

For `rates.pdf`, optionally add `rates.pdf.meta.json`:

```json
{
  "title": "Your schedule title",
  "authority": "cpwd",
  "state": "Delhi",
  "discipline": "civil",
  "version": "2026",
  "effective_from": "2026-01-01",
  "url": "https://the-official-source.example/document.pdf",
  "kind": "schedule"
}
```

Files without metadata are still indexed as unclassified candidates. Searchable
text does not become an approved official rate automatically. Import a structured
domain package to connect verified source rows to measurement recipes and rates;
then review it through the knowledge screen. Scanned PDFs without extractable text
are reported as requiring OCR; the app does not guess their contents.

See `examples/` and `docs/ingestion.md` for structured formats. Do not place API keys
or other secrets in this directory. In production, configure this folder for one
named tenant using `TENDER_DATABASE_TENANT`; uploaded sources stay tenant-scoped.
