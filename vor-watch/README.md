# VoR Watch

An independent reader or small journal can preserve a published PDF and check its next edition. VoR Watch records the exact file bytes, identifies pages with changed text or appearance, and creates a public change notice. If the editor has issued a correction, the same notice can link to it. This implementation and its historical dataset address Smart Scholars Open Problem 19.

## Three publisher records

Each JSON record pairs the original article DOI with its official correction DOI and the SHA-256 hashes of two genuine published PDFs. Each article had an announced correction. The dates below are the publisher’s historical edition dates. All files were retrieved for this retrospective comparison on November 20, 2026.

| Publisher | Editions compared | Result verified in the PDFs | Independent change record | Publisher notice |
| --- | --- | --- | --- | --- |
| PLOS | Aug 4 and Sep 24, 2020 | Page 7, Definition 4. The natural-gradient objective’s codomain changed from ℝⁿ to ℝ. Page 1 retained the same text and pixels. | [PLOS record](notices/plos.json) | [10.1371/journal.pone.0243330](https://doi.org/10.1371/journal.pone.0243330) |
| MDPI | Apr 20, 2018 and Jun 2, 2020 | Page 11, section 4.1. The revision specifies the simulated noise and pixel masking used to form the input images. Page 2 retained the same text and pixels. | [MDPI record](notices/mdpi.json) | [10.3390/ma13112436](https://doi.org/10.3390/ma13112436) |
| eLife | Feb 1 and Mar 31, 2016 | Page 5, Figure 3H. At 87% across the plot, digitizing the model’s lower trace against each version’s own axis gave approximately 0.445 and 0.322. These are measurements of the drawing. The authors say the correction affected visualization. | [eLife record](notices/elife.json) | [10.7554/eLife.16332](https://doi.org/10.7554/eLife.16332) |

[Six original PDF source links and byte checksums](cases.json) · [Independent spot-check measurements](spot_checks.json)

## Reproduce the audit

On Python 3.11 or later, install the one dependency. The reference reports were built with PyMuPDF 1.26.6, linked to MuPDF 1.26.11. A different platform or renderer can produce different pixels. The file hashes can be checked on any platform. The six PDFs total roughly 29 MB and are retrieved on demand.

```sh
python -m pip install -r requirements.txt
python reproduce.py
python verify_cases.py
python -m unittest -v test_vorwatch test_observe
```

`reproduce.py` downloads the two files for each article, checks all six SHA-256 values, rebuilds the three published notices, and compares each entire notice to the saved JSON. Later runs can use `python reproduce.py --offline`. `verify_cases.py` independently reads the PDFs to check the scientific examples above. For a human-readable line diff, try `python read_diff.py cache/plos/before.pdf cache/plos/after.pdf 7`.

PLOS supplies both historical editions as S1 and S2 of its correction notice. MDPI’s version notes name both publication dates. The preserved 2018 PDF is a publisher-formatted copy in the NCBI PubMed Central Open Access archive and the revised PDF comes from MDPI. The [eLife versions API](https://api.elifesciences.org/articles/09651/versions) identifies editions 2 and 3 as versions of record. Its earlier accepted manuscript was excluded. Article titles, authors and source links are in [cases.json](cases.json).

## Monitor one article independently

A library can run the following command after its regular download of an article’s current public PDF. A journal can also run it when releasing a new PDF. Use the same canonical DOI URL and archive directory each time. `observe.py` supports Linux and macOS. It reads the local file and writes only to the nominated archive directory.

```sh
python observe.py archive https://doi.org/10.1371/journal.pone.0236661 cache/plos/before.pdf
python observe.py archive https://doi.org/10.1371/journal.pone.0236661 cache/plos/before.pdf
python observe.py archive https://doi.org/10.1371/journal.pone.0236661 cache/plos/after.pdf
```

The first call records a baseline. The second leaves the ledger unchanged. The third publishes a hash-named JSON file in the local archive and adds its relative link to `records.json`. During a real deployment, publish these JSON files from an independently controlled static site or versioned repository. Keep PDF snapshots privately where redistribution rights require it. Retain an independent copy of the initial hash to establish continuity. A locally recorded observation time is a statement by the recorder. An independent repository, timestamping service or archival deposit can establish when that observation was publicly available.

If an official correction exists at capture time, add `--official-notice https://doi.org/...` to the changed-file call. If it is learned later, write a supplemental notice with the `compare` command and publish it beside the earlier notice. Both carry the same stable `transition_id`, computed from the DOI and the two exact file hashes. The `notice_id` binds the accompanying analysis and publisher link. `official_notice: null` means a URL was not supplied to that run. No inference about a publisher’s actions follows from that field.

```sh
python vorwatch.py compare cache/plos/before.pdf cache/plos/after.pdf \
  --article https://doi.org/10.1371/journal.pone.0236661 \
  --official-notice https://doi.org/10.1371/journal.pone.0243330 --out linked-notice.json
python vorwatch.py verify cache/plos/before.pdf cache/plos/after.pdf linked-notice.json
```

## Interpreting changes

The exact file hash detects a byte change to an observed PDF, including changes too small for a renderer to display. Identical bytes establish an exact match subject to the usual cryptographic collision assumption. A byte change can also come from metadata, timestamps or compression. Text extraction and rendering make the visible differences inspectable. Each changed page includes a text-line location when available and changed tiles on an eight-by-eight grid, numbered from the top left, when its appearance changes. A small vector or raster plot edit can therefore be detected even if the page’s extracted text is unchanged. A byte change with identical rendering and text is reported separately.

The PLOS pair matched on 7 of 29 same-position pages in both text and rendering. The MDPI pair matched on 10 of 20. eLife grew from 29 to 30 pages, and line wrapping or new page numbers can produce a visually changed page throughout a document. The case-specific checks identify a particular scientific change and two unchanged historical pages independently of those page counts. These three deliberately selected positives demonstrate behavior. They do not estimate a population-wide error rate.

Coverage requires access to both editions. A replacement posted and removed between observations can be missed. Embedded data, HTML pages and external supplementary files require their own captures. PDF appearance comparisons depend on rendering resolution, fonts, and renderer version. A change record reports the observable difference and links to the editorial account when available. It does not determine the cause of a revision.

## Attribution and AI assistance

Article authors retain credit for their papers. The original publications are Wensing and Slotine (PLOS), Li and Liang (MDPI), and Peters and Lau (eLife). This repository includes links, checksums and derived measurements. Readers retrieve the PDFs from the listed public sources. AI assistance was used to locate public historical editions, implement the software and checks, and prepare the documentation. The measurements and pass/fail results are computed from the source PDFs and can be rerun.
