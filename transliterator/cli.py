#!/usr/bin/env python3
"""
Transliterator CLI

Command-line interface for faithful document-to-markdown conversion.

Usage:
    python -m transliterator <source> [options]
    python -m transliterator document.pdf
    python -m transliterator https://example.com
    python -m transliterator https://company.sharepoint.com/sites/policies/doc.aspx
    python -m transliterator ./documents/             # convert all files in directory
    python -m transliterator file1.pdf file2.docx     # convert multiple files

Options:
    -o, --output DIR     Output directory (default: ./transliterator_output)
    --stdout             Print to stdout instead of saving files
    --formats            Show all supported formats
"""

import argparse
import sys
import os

# Allow running from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transliterator.core import Transliterator


def main():
    parser = argparse.ArgumentParser(
        prog="transliterator",
        description=(
            "Faithful Document-to-Markdown Transliterator\n\n"
            "Converts PDFs, web pages, SharePoint links, images, and Office\n"
            "documents into clean, structured Markdown. No AI interpretation\n"
            "— just precise structural transliteration."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m transliterator policy.pdf\n"
            "  python -m transliterator https://company.sharepoint.com/sites/HR/policy.aspx\n"
            "  python -m transliterator ./policies/                    # whole directory\n"
            "  python -m transliterator doc1.pdf doc2.docx image.png   # multiple files\n"
            "  python -m transliterator report.pdf --stdout             # print to terminal\n"
            "  python -m transliterator report.pdf -o ./markdown_out   # custom output dir\n"
        ),
    )

    parser.add_argument(
        "sources",
        nargs="*",
        help="Files, directories, or URLs to convert",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: ./transliterator_output)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print Markdown to stdout instead of saving to files",
    )
    parser.add_argument(
        "--formats",
        action="store_true",
        help="Show all supported input formats and exit",
    )

    args = parser.parse_args()

    if args.formats:
        _show_formats()
        return

    if not args.sources:
        parser.print_help()
        print("\nError: No sources provided. Specify files, directories, or URLs to convert.")
        sys.exit(1)

    engine = Transliterator(output_dir=args.output)
    save = not args.stdout

    print("=" * 60)
    print("  TRANSLITERATOR - Faithful Document-to-Markdown Converter")
    print("=" * 60)
    print()

    success_count = 0
    error_count = 0

    for source in args.sources:
        try:
            md_text = engine.convert(source, save=save)
            if args.stdout:
                print(md_text)
                print("\n" + "=" * 60 + "\n")
            success_count += 1
        except Exception as e:
            print(f"[ERROR] {source}: {e}", file=sys.stderr)
            error_count += 1

    print()
    print("-" * 60)
    print(f"  Done: {success_count} converted, {error_count} errors")
    if save:
        print(f"  Output: {engine.output_dir}")
    print("-" * 60)


def _show_formats():
    """Display all supported formats."""
    formats = Transliterator.supported_formats()
    print("\nSupported Input Formats:")
    print("-" * 40)
    for category, extensions in formats.items():
        print(f"\n  {category}:")
        for ext in extensions:
            print(f"    {ext}")
    print()


if __name__ == "__main__":
    main()
