# Sphinx configuration for music-daily-recs-ebook

project = "Music Daily Recs Pipeline"
copyright = "2026, Hermes Agent"
author = "Hermes Agent"
release = "1.0"

extensions = [
    "sphinx_rtd_theme",
    "sphinxcontrib.mermaid",
]

mermaid_version = "11"
mermaid_procs = "2"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 4,
    "titles_only": False,
}

html_static_path = ["_static"]

source_suffix = ".rst"
master_doc = "index"
