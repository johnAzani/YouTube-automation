#!/usr/bin/env python3
"""CLI script to build and export Selar Digital Products for The Secret Place.

Generates:
  1. 1080x1080 DOCOGA REELS v2 sapphire glassmorphic product covers.
  2. JSON listing specifications ready to copy-paste into Selar.co.
  3. Formatted printable prayer journal markdown & text deliverables.

Usage:
    python3 scripts/build_selar_products.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.selar_store import (
    CANONICAL_SELAR_PRODUCTS,
    PRODUCTS_DIR,
    export_selar_product_manifests,
)


def main():
    parser = argparse.ArgumentParser(description="Selar Digital Store & Products Builder ($0.00 Lock)")
    parser.add_argument("--out-dir", type=str, default=str(PRODUCTS_DIR), help="Output directory for products")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    print("==========================================================================")
    print("THE SECRET PLACE — SELAR DIGITAL STORE & PRODUCTS BUILDER")
    print("Target Payout:   First Bank of Nigeria USD Domiciliary Account (FBNINGLA)")
    print("Currency:        USD, GBP, EUR, NGN (Global Checkout)")
    print("Cost Invariant:  $0.00 / month forever (Pay-What-You-Want Digital Model)")
    print("==========================================================================")

    files = export_selar_product_manifests(out_dir)
    print(f"[*] Generated {len(files)} product assets in {out_dir.relative_to(REPO_ROOT)}:")
    for f in files:
        size_kb = f.stat().st_size / 1024
        print(f"    • {f.name} ({size_kb:.1f} KB)")

    print("\n[+] Product Catalog Summary:")
    for p in CANONICAL_SELAR_PRODUCTS:
        pricing = f"Pay-What-You-Want (Suggested ${p.suggested_usd:.2f})" if p.is_pay_what_you_want else f"${p.price_usd:.2f}"
        print(f"  • [{p.product_id}] {p.title}")
        print(f"    Price: {pricing} | Cover: {p.cover_image_name}")

    print("==========================================================================")
    print("Ready to list on Selar.co! See docs/SELAR_NIGERIA_SETUP.md for 3-minute guide.")
    print("==========================================================================")


if __name__ == "__main__":
    main()
