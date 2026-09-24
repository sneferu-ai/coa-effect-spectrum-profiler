# Product guide — COA Effect-Spectrum Profiler

This guide is for the person using the tool: a Florida medical-cannabis patient
holding a Certificate of Analysis (COA) from a dispensary purchase. It covers
the whole journey — opening the site, uploading the certificate, reading the
result, and keeping the PDF — plus what to do when something goes wrong.

Running the server itself is an operator task; see the
[README](../README.md) and [OPERATIONS.md](OPERATIONS.md).

## What this tool does

You give it the Certificate of Analysis that came with your product — the lab
report listing measured cannabinoids and terpenes. The tool reads the chemistry
printed on that document and computes a **placement on a 0–100 sativa↔indica
tendency scale** (0 = sativa-leaning, 100 = indica-leaning), with a
plain-language explanation and a one-page PDF profile you can keep.

The placement is a **chemistry-derived tendency, not an effect prediction** and
not medical advice. The sativa/indica categories are botanical labels, not
validated chemical categories, and published studies suggest strain labels
often correlate poorly with chemical composition — which is why this tool reads
the chemistry, not the label. Your individual response depends on dose,
tolerance, and biology, none of which appear on a certificate. The full scoring
method, weights, and citations are public on the **How it works** page
(`/algorithm`) and in [algorithm.md](algorithm.md).

## Access and sign-in

**There is no account and no sign-in.** The tool is free and asks for nothing
but the certificate file. Anyone with the URL can use it. The only cookie the
site sets is one short-lived, functional session cookie that holds your result
for a few minutes (see "Your privacy" below).

## What you need before you start

- The **Certificate of Analysis** for your product, as a PDF (for example,
  downloaded from the dispensary or scanned by the lab) or a photo saved as
  **JPEG, PNG, or HEIC**.
- File size under the limit shown on the upload page (15 MB by default).
- For photos: good light, the document flat and straight-on, filling the frame.

Florida-format certificates (issued under the state's OMMU testing rules) are
the supported input at launch. Certificates from other states may parse through
the generic reader, but they are outside the tested scope.

## The primary journey, start to finish

1. **Open the tool.** Go to the site's address (for a locally running server,
   `http://localhost:8080/`). You land on the upload page.
2. **Select your certificate.** Tap or click the drop zone ("Drop a PDF or
   photo here, or tap to choose a file") and pick the file, or drag the file
   onto the zone. The button reads **Analyze my COA** and stays disabled until
   a file is selected.
3. **Wait for the reading.** An overlay tells you the document is being read.
   Reading typically takes seconds and is bounded well under two minutes; a
   scanned or photographed page takes longer than a PDF because it goes through
   OCR.
4. **Read your result.** The results page shows:
   - your **placement** on the spectrum bar (for example, "Placement: 70 of
     100 — indica-leaning"), with a shaded **uncertainty band** around the
     marker;
   - the **confidence readout** — "Data completeness: X%. Model confidence:
     Y%. Combined: Z%." Confidence reflects how much of your certificate was
     readable and a judgment about the published evidence — never the certainty
     of your individual experience;
   - **What drove this placement** — the two or three compounds that mattered
     most, with the values as printed on your certificate;
   - the **full chemistry table**, with each value marked *verified*, *derived*
     (computed from THCA/CBDA when the lab printed no total), or *unreadable*
     — the tool flags what it cannot read and never guesses. Expandable rows
     show the exact span of document text each value came from.
5. **Download the PDF profile.** Tap **Download PDF profile**. The one-page
   profile carries the placement, band, confidence, chemistry summary,
   rationale, and disclaimer. It is the copy to keep — the web result itself is
   temporary (next section).
6. **Optionally: download the raw data** (JSON) or **tell us if it helped**
   with the 👍/👎 feedback buttons on the results page. Both require
   JavaScript; everything else works without it.
7. **Done — or analyze another.** Tap **Analyze another COA**. This erases the
   current session and returns you to the upload page.

### If the certificate is only partly readable

- **Degraded placement.** Your cannabinoids were read but the terpene panel was
  missing or mostly unreadable. You still get a placement, computed from the
  THC:CBD ratio alone, with a clearly visible notice that cannabinoid ratios
  are particularly contested predictors, a wider uncertainty band, and a lower
  confidence score. If combined confidence falls below the floor, the tool
  refuses to place at all rather than pretend precision.
- **Refusal (chemotype summary only).** Zero terpenes readable: no placement,
  no spectrum bar. You get the chemistry table of what *was* read and the
  reason in plain words.

## Your privacy, in practice

- **Nothing is stored on the server.** There is no database and no account.
  Your file is processed in memory; the working copy lives in a temporary
  folder that is deleted when your session ends.
- **Sessions last 5 minutes** by default. When the time is up — or when you tap
  **Analyze another COA** — the result is gone from the server and `/result`
  answers "session ended" (HTTP 410). The PDF you downloaded is yours and is
  unaffected.
- The only cookie is the functional session cookie (`HttpOnly`,
  `SameSite=Strict`). No analytics, no tracking pixels, no third-party
  resources.
- The server's access log records IP addresses in a configurable form
  (hashed with a daily salt by default). The full statement is on the
  **Privacy** page (`/privacy`).

## Restart and recovery

- **You closed the browser or the tab:** if fewer than 5 minutes passed, return
  to the site — the session cookie still opens your result. After that, upload
  again. Nothing can be recovered after expiry because nothing is retained.
- **The server restarted while you were reading:** in-memory sessions do not
  survive a restart. Upload the certificate again — the computation is
  deterministic, so the same document yields the same placement.
- **Verify your saved work:** open the downloaded PDF. It contains the
  placement, the scorer version, and the hash of the weight table used, so any
  later result can be compared against it.

## In-product help

- **"What is a Certificate of Analysis?"** — expandable explainer on the upload
  page.
- **How it works** (`/algorithm`) — the complete weight table, formulas,
  confidence rule, degradation rules, and literature citations, linked from the
  results page, the PDF footer, and the privacy page.
- **Privacy** (`/privacy`) — what is and is not recorded.
- **Contact** — the landing page carries a `mailto:` link for batch-processing
  inquiries; it opens your email client and sends nothing until you do.

## Common errors and exactly what to do

Every error page shows a reference code. Find it below.

| Reference | What it means | What to do |
|---|---|---|
| `INVALID_FILE_TYPE` | The file is not a PDF, JPEG, PNG, or HEIC — checked by content, not by file extension. | Upload the original PDF from the dispensary, or a clear photo saved as JPEG, PNG, or HEIC. |
| `FILE_TOO_LARGE` | The file exceeds the upload limit (15 MB by default). | Use a smaller photo or the original PDF. |
| `HEIC_UNSUPPORTED` | The server cannot read HEIC photos right now. | Re-save or screenshot the photo as JPEG or PNG, then upload that. |
| `NOT_A_COA` | No certificate-of-analysis structure was found (no cannabinoid table or certificate header). | Upload the certificate that came with the product — not a receipt, label, or menu. |
| `UNREADABLE_DOCUMENT` | The photo or scan is too unclear to read reliably; the tool never guesses. | Retake the photo in good light, flat and straight-on, filling the frame — or upload the original PDF. |
| `NO_USABLE_CHEMISTRY` | A certificate-like document was found, but no cannabinoid or terpene value could be read. | Try a sharper photo or the original PDF. |
| `PROCESSING_TIMEOUT` | Reading took longer than the time limit. | Try again; if it repeats, upload a smaller or clearer file. |
| `RATE_LIMITED` | Too many uploads in a short time (HTTP 429, with a wait time). | Wait the indicated number of seconds and try again. |
| `SERVER_BUSY` | The analysis queue is full (HTTP 503). | Wait about 30 seconds and try again. |
| `METADATA_SCRUB_FAILED` | The file could not be copied privately, so it was discarded. | Re-save the file or take a fresh photo, then upload again. |
| `SESSION_EXPIRED` | Your 5-minute session ended (HTTP 410). | Upload the certificate again to get a new result. |

If an error persists across retries and different files, use the contact link
on the landing page.

## What this tool does not do

- No effect predictions, dosing, or health statements — by design, enforced by
  an automated banned-lexicon check over every page and generated sentence.
- No strain-name lookup without an uploaded certificate.
- No accounts, saved history, payments, product menus, or shopping links.
