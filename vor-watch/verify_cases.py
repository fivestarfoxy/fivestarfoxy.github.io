"""Verify selected page content against three public correction notices, independently of the detector."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
from statistics import median
import unicodedata

import fitz


def page_text(doc, number):
    text = unicodedata.normalize("NFKC", doc[number - 1].get_text())
    return " ".join(text.split())


def check(condition, message):
    if not condition:
        raise ValueError(message)


def unchanged_page(before, after, number):
    text = page_text(before, number)
    check(len(text) > 1000 and text == page_text(after, number),
          f"Negative control failed on page {number}: text differs or is missing")
    first = before[number - 1].get_pixmap()
    last = after[number - 1].get_pixmap()
    check((first.width, first.height, first.samples) == (last.width, last.height, last.samples),
          f"Negative control failed on page {number}: rendered pixels differ")
    return {"page": number, "same_normalized_text": True, "same_72dpi_pixels": True}


def plos(before, after):
    prefix = "The natural gradient of a differentiable function f : Rn ! "
    suffix = " is the direction of steepest ascent"
    for doc, codomain in ((before, "Rn"), (after, "R")):
        check(prefix + codomain + suffix in page_text(doc, 7),
              f"Expected the natural-gradient definition with codomain {codomain} on page 7")
    return {"page": 7, "location": "Definition 4, scalar objective in the natural-gradient definition",
            "before": "codomain R^n", "after": "codomain R",
            "negative_control": unchanged_page(before, after, 1)}


def mdpi(before, after):
    for doc, phrase in ((before, "images re-cquisition"), (after, "images re-acquisition")):
        check(phrase in page_text(doc, 1), f"Expected {phrase!r} on page 1")
    before_text = page_text(before, 11)
    after_text = page_text(after, 11)
    check("residues on the AA7075 sample surface" in before_text, "Page 11 original passage is missing")
    for phrase in ("adding Gaussian and impulse noises", "pixel masking operation"):
        check(phrase not in before_text and phrase in after_text,
              f"Expected the revised contamination procedure {phrase!r} on page 11")
    return {"page": 11, "location": "Section 4.1, final paragraph",
            "before": "Mentions contamination residues on the AA7075 sample surface.",
            "after": "Specifies added Gaussian and impulse noise and artificial pixel masking.",
            "additional_control": {"page": 1, "before": "re-cquisition", "after": "re-acquisition"},
            "negative_control": unchanged_page(before, after, 2)}


def read_panel_h(doc):
    """Digitize the lower trace at 87% of panel H's plot width, using printed axes in each image."""
    page = doc[4]
    check("Figure 3. Group-level results" in page_text(doc, 5), "Expected Figure 3 on page 5")
    images = [item for item in page.get_image_info(xrefs=True) if item["width"] > 1000]
    check(len(images) == 1 and images[0]["xref"] > 0, "Expected a single high-resolution Figure 3")
    gray = fitz.Pixmap(fitz.csGRAY, fitz.Pixmap(doc, images[0]["xref"]))
    w, h = gray.width, gray.height
    pixels = gray.samples_mv

    def at(x, y):
        return pixels[y * gray.stride + x]

    def longest_rule(y_start, y_end, x_start, x_end, threshold):
        return max(range(int(h * y_start), int(h * y_end)),
                   key=lambda y: sum(at(x, y) < threshold for x in range(x_start, x_end)))

    # Locate this panel's vertical and horizontal axes separately in each source.
    axis_x = max(range(int(.43 * w), int(.46 * w)),
                 key=lambda x: sum(at(x, y) < 190 for y in range(int(.69 * h), int(.93 * h))))
    right_limit = int(.69 * w)
    base_y = longest_rule(.90, .947, axis_x, right_limit, 190)
    right_x = max(x for x in range(axis_x, right_limit) if at(x, base_y) < 190)
    top_y = next(y for y in range(int(.675 * h), base_y) if at(axis_x, y) < 190)
    # Top tick = 1.0, dotted horizontal reference = 0.5. The lower axis limit
    # changed between versions, so using the bottom edge to scale both would be incorrect.
    half_y = longest_rule(.845, .90, axis_x + 5, right_x - 5, 200)
    sample_x = int(axis_x + .87 * (right_x - axis_x))
    trace = [y for y in range(half_y + 2, base_y - 1) if at(sample_x, y) < 125]
    check(bool(trace) and top_y < half_y < base_y, "Could not locate the lower trace in Figure 3H")
    return round(.5 - .5 * (median(trace) - half_y) / (half_y - top_y), 3)


def elife(before, after):
    old = read_panel_h(before)
    new = read_panel_h(after)
    check(.42 < old < .47 and .29 < new < .35, "Figure 3H lower trace does not match the historical pair")
    return {"page": 5, "location": "Figure 3H, model row, lower false-alarm-rate trace",
            "measurement": "approximate plotted y at 87% of the panel's horizontal axis",
            "before": old, "after": new}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_root", nargs="?", default=Path("cache"), type=Path,
                        help="directory containing {plos,mdpi,elife}/{before,after}.pdf")
    args = parser.parse_args()
    result = {}
    for publisher, verify in (("plos", plos), ("mdpi", mdpi), ("elife", elife)):
        with ExitStack() as files:
            before, after = [files.enter_context(fitz.open(args.input_root / publisher / name))
                             for name in ("before.pdf", "after.pdf")]
            result[publisher] = verify(before, after)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
