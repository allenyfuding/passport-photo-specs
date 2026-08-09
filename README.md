# Official Passport & Visa Photo Specifications

Machine-readable, community-verified specifications for passport and visa photos
across the US, UK, Canada and India.

Maintained by [ExamIDPhoto](https://examidphoto.com) — an online passport and visa
photo service. We re-verify every spec against the official government source and
stamp each entry with its verification date, so you can trust the freshness.

## Files

- `passport_photo_specs.json` — full dataset (structured)
- `passport_photo_specs.csv` — same data as a spreadsheet-friendly CSV

## Coverage

| ID | Document | Size | Head height | Background |
|----|----------|------|-------------|------------|
| us_passport | US Passport | 2x2 in (51x51 mm) | 25-35 mm (50-69%) | White/off-white |
| uk_passport | UK Passport | digital >=600x750 px / 45x35 mm | 29-34 mm (64-76%) | Plain light |
| ca_passport | Canada Passport (online renewal) | 1200x1800 px | 45-50% of height | Pure white |
| us_visa | US Visa (DS-160) | 600x600 px | 50-69% of height | White/off-white |
| uk_visa | UK Visa | digital >=600x750 px | head/shoulders in frame | Light, no shadows |
| ca_visa | Canada Visa / TR | 35x45 mm | 31-36 mm (69-80%) | Plain white |
| in_evisa | India e-Visa | 600x600 px | ~64.5% of height | Light/white |

## Sources

All entries cite the official government source (travel.state.gov, gov.uk,
canada.ca, indianvisaonline.gov.in) with a `verified_date` in the dataset.
Last full re-check: 2026-08-08.

## Disclaimer

Requirements change. Always confirm against the official government source before
submitting an application. This dataset is informational and is not legal advice.
