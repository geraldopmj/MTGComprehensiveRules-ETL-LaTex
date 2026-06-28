from mtg_rules_etl.cli import create_parser


def test_cli_defaults_use_latex_directory():
    args = create_parser().parse_args([])

    assert args.rules_tex == "latex/rules.tex"
    assert args.cover_tex == "latex/mtg_rules.tex"
