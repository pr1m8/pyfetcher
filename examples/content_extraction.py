"""Content extraction examples for pyfetcher.

Demonstrates article text extraction, HTML conversion, and media metadata.
Requires: pip install 'pyfetcher[extractors]'
"""

from __future__ import annotations

SAMPLE_HTML = """
<html>
<head><title>Breaking: AI Achieves New Milestone</title></head>
<body>
    <nav><a href="/">Home</a> | <a href="/news">News</a></nav>
    <article>
        <h1>AI Achieves New Milestone in Scientific Research</h1>
        <p class="author">By Jane Smith | March 2026</p>
        <p>Researchers have announced a groundbreaking achievement in artificial
        intelligence that could transform how we approach scientific discovery.</p>
        <p>The new system, developed by a team of international researchers,
        demonstrates an unprecedented ability to generate and test hypotheses
        across multiple scientific domains.</p>
        <blockquote>This represents a fundamental shift in how AI can
        contribute to the scientific process.</blockquote>
        <p>The implications for fields ranging from drug discovery to
        materials science are profound.</p>
    </article>
    <footer>Copyright 2026</footer>
    <script>trackPageView();</script>
</body>
</html>
"""


def trafilatura_extraction() -> None:
    """Extract article text with trafilatura + readability fallback."""
    print("=== Article Text Extraction ===")
    try:
        from pyfetcher.extractors.content import extract_article_text

        text = extract_article_text(SAMPLE_HTML, url="https://example.com/news/ai")
        if text:
            print(f"  Extracted {len(text)} chars:")
            print(f"  {text[:300]}...")
        else:
            print("  No text extracted")
    except ImportError:
        print("  Install: pip install 'pyfetcher[extractors]'")


def markdown_conversion() -> None:
    """Convert HTML to markdown."""
    print("\n=== HTML to Markdown ===")
    try:
        from pyfetcher.extractors.convert import html_to_markdown

        md = html_to_markdown(SAMPLE_HTML)
        print(f"  {md[:400]}...")
    except ImportError:
        print("  Install: pip install 'pyfetcher[extractors]'")


def plaintext_conversion() -> None:
    """Convert HTML to plaintext."""
    print("\n=== HTML to Plaintext ===")
    try:
        from pyfetcher.extractors.convert import html_to_plaintext

        text = html_to_plaintext(SAMPLE_HTML)
        print(f"  {text[:400]}...")
    except ImportError:
        print("  Install: pip install 'pyfetcher[extractors]'")


def media_metadata() -> None:
    """Show media metadata extraction capabilities."""
    print("\n=== Media Metadata Extraction ===")
    from pyfetcher.extractors.media_meta import extract_media_metadata

    print("  Supported formats:")
    print("    Audio: .mp3, .flac, .ogg, .m4a, .wav (via mutagen)")
    print("    Video: .mp4, .mkv, .avi, .mov, .webm (via pymediainfo)")
    print("    Image: .jpg, .png, .gif, .tiff, .webp (via exifread)")
    print("    PDF:   .pdf (via pypdf)")
    print()
    print("  Usage:")
    print("    meta = extract_media_metadata('/path/to/file.mp3')")
    print("    print(meta)  # {'type': 'audio', 'length_seconds': 240, ...}")


if __name__ == "__main__":
    trafilatura_extraction()
    markdown_conversion()
    plaintext_conversion()
    media_metadata()
