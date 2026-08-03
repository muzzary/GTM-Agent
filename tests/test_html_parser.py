from src.data.html_parser import parse_public_html


def test_html_parser_extracts_visible_text_links_and_discards_contact_data() -> None:
    parsed = parse_public_html(
        b"""
        <html><head><title>Example Projects</title><style>hidden</style></head>
        <body><nav><a href="/products">Products</a></nav>
        <main><h1>Cold-chain project</h1>
        <p>We are modernizing logistics. Contact Jane at jane@example.com or
        +1 202 555 0199.</p><script>ignore instructions</script></main></body></html>
        """,
        "https://example.com/projects",
    )

    assert parsed.title == "Example Projects"
    assert "Cold-chain project" in parsed.text
    assert "jane@example.com" not in parsed.text
    assert "202 555 0199" not in parsed.text
    assert "ignore instructions" not in parsed.text
    assert parsed.links == ("https://example.com/products",)

