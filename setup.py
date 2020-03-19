from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
setup(
    name="Werkzeug",
    extras_require={
        "watchdog": ["watchdog"],
        "dev": [
            "pytest",
            "pytest-timeout",
            "tox",
            "sphinx",
            "pallets-sphinx-themes",
            "sphinxcontrib-log-cabinet",
            "sphinx-issues",
        ],
    },
)
