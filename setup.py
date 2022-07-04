from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
setup(
    name="Werkzeug",
    install_requires=["MarkupSafe>=2.1.1"],
    extras_require={"watchdog": ["watchdog"]},
)
