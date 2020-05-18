from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
setup(name="Werkzeug", extras_require={"watchdog": ["watchdog"]})
