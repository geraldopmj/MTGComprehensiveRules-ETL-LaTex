from mtg_rules_etl.source import extract_txt_link


def test_extract_txt_link_from_rules_page_html():
    html = """
    <html>
      <body>
        <a href="https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf">PDF</a>
        <a href="https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.txt">TXT</a>
      </body>
    </html>
    """

    assert extract_txt_link(html, "https://magic.wizards.com/en/rules") == (
        "https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.txt"
    )


def test_extract_txt_link_percent_encodes_spaces_from_official_html():
    html = """
    <a href="https://media.wizards.com/2026/downloads/MagicCompRules 20260619.txt">TXT</a>
    """

    assert extract_txt_link(html, "https://magic.wizards.com/en/rules") == (
        "https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.txt"
    )
