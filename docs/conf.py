from pallets_sphinx_themes import get_version
from pallets_sphinx_themes import ProjectLink

# Project --------------------------------------------------------------

project = "Werkzeug"
copyright = "2007 Pallets"
author = "Pallets"
release, version = get_version("Werkzeug")

# General --------------------------------------------------------------

master_doc = "index"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "pallets_sphinx_themes",
    "sphinx_issues",
    "sphinxcontrib.log_cabinet",
]
autoclass_content = "both"
autodoc_typehints = "description"
intersphinx_mapping = {"python": ("https://docs.python.org/3/", None)}
issues_github_path = "pallets/werkzeug"

# HTML -----------------------------------------------------------------

html_theme = "werkzeug"
html_context = {
    "project_links": [
        ProjectLink("Donate", "https://palletsprojects.com/donate"),
        ProjectLink("PyPI Releases", "https://pypi.org/project/Werkzeug/"),
        ProjectLink("Source Code", "https://github.com/pallets/werkzeug/"),
        ProjectLink("Issue Tracker", "https://github.com/pallets/werkzeug/issues/"),
        ProjectLink("Website", "https://palletsprojects.com/p/werkzeug/"),
        ProjectLink("Twitter", "https://twitter.com/PalletsTeam"),
        ProjectLink("Chat", "https://discord.gg/pallets"),
    ]
}
html_sidebars = {
    "index": ["project.html", "localtoc.html", "searchbox.html"],
    "**": ["localtoc.html", "relations.html", "searchbox.html"],
}
singlehtml_sidebars = {"index": ["project.html", "localtoc.html"]}
html_static_path = ["_static"]
html_favicon = "_static/favicon.ico"
html_logo = "_static/werkzeug.png"
html_title = f"Werkzeug Documentation ({version})"
html_show_sourcelink = False

# LaTeX ----------------------------------------------------------------

latex_documents = [
    (master_doc, f"Werkzeug-{version}.tex", html_title, author, "manual")
]
