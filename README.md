# Official Passport & Visa Photo Specifications

Machine-readable, community-verified specifications for passport and visa photos
across the US, UK, Canada, India and more.

Maintained by [ExamIDPhoto](https://examidphoto.com) — an online passport and visa
photo service. We re-verify every spec against the official government source and
stamp each entry with its verification date, so you can trust the freshness.

## Files

- `passport_photo_specs.json` — full dataset (structured)
- `passport_photo_specs.csv` — same data as a spreadsheet-friendly CSV

## Coverage

| ID | Document | Size | Head height | Background |
|----|----------|------|-------------|------------|
| us_passport | US Passport | 2x2 in (51x51 mm) | 25-35 mm (about 50-69% of photo height) | Plain white or off-white |
| uk_passport | UK Passport | Digital >=600x750 px; printed 45x35 mm | Head height (crown to chin) 29-34 mm (64-76% of photo height) | Plain light-coloured (digital); plain cream or light grey (printed) |
| ca_passport | Canada Passport (online renewal) | Digital 3:2 portrait (official 1200x1800-3000x4500 px) | Head height (chin to top of head) 45-50% of photo height | Pure white or light |
| us_visa | US Visa (DS-160) | 2x2 in (51x51 mm) | Head height 50-69% of photo height | Plain white or off-white |
| uk_visa | UK Visa | Digital >=600x750 px (no printed step) | Head, shoulders and upper body in frame (official digital rule) | Plain light-coloured, no shadows |
| ca_visa | Canada Visa / Temporary Resident | 35x45 mm | Head height 31-36 mm (69-80% of photo height) | Plain white |
| in_evisa | India e-Visa | 2x2 in (51x51 mm) @300 dpi | Head height about 64.5% of photo height (crown to chin) | Plain light / white |
| cn_passport | China Passport | 33x48 mm | Head height (top of hair to chin) about 31.5 mm; 5 mm from top of photo to top of hair | White or light background |
| cn_visa_online | China Visa (online photo) | 354x472 px | Head height about 356 px; 25 px from top of photo to top of hair | White background |
| sg_passport | Singapore Passport | Digital 400x514 px (e-services upload) | ISO/ICAO-based head proportions (ICA references ISO & ICAO specifications) | Plain white or light background |
| my_evisa | Malaysia e-Visa | 35x50 mm | Head height (top of hair) about 32.5 mm; 5 mm from top of photo to top of hair | White background |
| vn_visa | Vietnam e-Visa | 40x60 mm | Head height (top of hair) about 40 mm; 6 mm from top of photo to top of hair | White background |
| ae_visa | UAE Visa | 43x55 mm | Head height (top of hair) about 40 mm; 5 mm from top of photo to top of hair | White background |
| sa_evisa | Saudi Arabia e-Visa | 200x200 px | Head height about 70% of photo height; 7% from top of photo to top of hair | White background |
| nz_passport | New Zealand Passport | Digital 1500x2000 px | Head height about 70% of photo height; eye line about 54% from bottom of photo | Plain light background |
| mm_visa | Myanmar e-Visa | 38x46 mm | Head height about 33 mm; 3 mm from top of photo to top of hair | White background |
| au_passport | Australia Passport | 35–40 x 45–50 mm (printed photos) | Face height (chin to crown) 32–36 mm | Plain white or light grey |
| au_visa | Australia Visa | 35–40 x 45–50 mm (passport-standard photo) | Face height (chin to crown) 32–36 mm | Plain white or light grey |
| uz_visa | Uzbekistan Visa | 35x45 mm | Head height (top of hair) about 34.5 mm; 3 mm from top of photo to top of hair | Plain background, no shadows |
| nz_visa_online | New Zealand Visa (online photo) | Digital JPG/JPEG, 3:4 portrait (online upload) | - | Plain, no shadows; good contrast with face |
| sg_visa_online | Singapore Visa (online photo) | 400x514 px | Head height (top of hair) about 74%; 9% from top of photo to top of hair | Plain white or light background |
| my_passport | Malaysia Passport | 35x50 mm | Head height (top of hair) about 29 mm; 10 mm from top of photo to top of hair | White background |
| in_passport_oci | India OCI (Overseas Citizen) — online photo | 2x2 in (51x51 mm), colour | Head height (top of hair to bottom of chin) 1 to 1-3/8 in (25–35 mm); eye height 1-1/8 to 1-3/8 in | Plain light-coloured background, no shadows |

## Sources

All entries cite an official or cross-checked source with a `verified_date`.
Entries verified against official pages on 2026-08-09: CN, SG-passport, NZ-visa,
AU-passport (passports.gov.au), IN-OCI (ociservices.gov.in PDF).
AU-visa follows the passport standard (Form 1419 PDF pending re-check).
UZ/MY/VN/AE/SA/MM/SG-visa are cross-checked against visafoto.com aggregation with
official links (pending browser re-check before production use).
Last full re-check: 2026-08-09.

## Auto-refresh (GitHub Action)

This repository re-verifies official sources automatically via
`.github/workflows/spec-sync.yml` (daily 03:17 UTC + manual dispatch):

- Fetches each official page and checks the key facts (size, head height,
  background, etc.) with stable regexes — wording-only changes do not bump dates.
- When the facts still match, the spec's `verified_date` is refreshed to the run
  date and `passport_photo_specs.csv` is regenerated from the JSON.
- When facts change, or a page is removed / returns an anomaly, **the spec values
  are never auto-edited** — an alert issue is opened for manual re-verification,
  and only then are the values (and date) updated by a human.
- Unreachable sources keep their previous `verified_date`; after 3 consecutive
  failures an alert is raised.

Run the verification locally at any time:

    python3 spec_fetch.py

Runtime state lives in `spec_watch/` (`state.json`, `REPORT.md`, `DRIFT.md`).

## Disclaimer

Requirements change. Always confirm against the official government source before
submitting an application. This dataset is informational and is not legal advice.
