#!/usr/bin/env python3
"""Embed exact C function excerpts in the offline visualizer after C edits."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def excerpts():
    text = (ROOT / "matmul.c").read_text()
    kernels = ("seq", "parallel_i", "parallel_j", "parallel_k", "collapse_ij",
               "collapse_jk", "collapse_ijk", "nested_ij", "nested_jk", "nested_ik",
               "nested_ijk", "hybrid_ij_k", "hybrid_i_jk")

    def extract(name):
        match = re.search(r"^static (?:inline )?\w+ " + re.escape(name) + r"\([^\n]*\) \{\n.*?^\}", text, re.M | re.S)
        if not match:
            raise ValueError(f"cannot find function {name}")
        return {"name": name, "startLine": text[:match.start()].count("\n") + 1, "text": match.group()}

    return {
        "file": "matmul.c", "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "kernels": {name: extract("sequential" if name == "seq" else name) for name in kernels},
        "helpers": {name: extract(name) for name in ("dot", "b_at", "schedule_at")},
    }


def main():
    page = ROOT / "interactive.html"
    data = json.dumps(excerpts(), ensure_ascii=False, indent=2).replace("<", "\\u003c")
    markup = '<script id="matrix-source" type="application/json">' + data + '</script>'
    text, count = re.subn(r'<script id="matrix-source" type="application/json">.*?</script>',
                         lambda _: markup, page.read_text(), flags=re.S)
    if count != 1:
        raise ValueError("expected exactly one matrix-source block")
    page.write_text(text)
    print("Embedded 13 kernels and 3 helpers from matmul.c.")


if __name__ == "__main__":
    main()
