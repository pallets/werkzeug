#
# Werkzeug Makefile
# ~~~~~~~~~~~~~~~~~
#
# Shortcuts for various tasks.
#
# :copyright: (c) 2008 by the Werkzeug Team, see AUTHORS for more details.
# :license: BSD, see LICENSE for more details.
#

documentation:
	@(cd docs; make html)

release:
	python scripts/make-release.py

test:
	py.test --tb=native

tox-test:
	tox

coverage:
	@(coverage run --source=werkzeug --module py.test $(TEST_OPTIONS) $(TESTS))

doctest:
	@(cd docs; sphinx-build -b doctest . _build/doctest)

upload-docs:
	$(MAKE) -C docs html dirhtml latex
	$(MAKE) -C docs/_build/latex all-pdf
	cd docs/_build/; mv html werkzeug-docs; zip -r werkzeug-docs.zip werkzeug-docs; mv werkzeug-docs html
	rsync -a docs/_build/dirhtml/ flow.srv.pocoo.org:/srv/websites/werkzeug.pocoo.org/docs/
	rsync -a docs/_build/latex/Werkzeug.pdf flow.srv.pocoo.org:/srv/websites/werkzeug.pocoo.org/docs/
	rsync -a docs/_build/werkzeug-docs.zip flow.srv.pocoo.org:/srv/websites/werkzeug.pocoo.org/docs/werkzeug-docs.zip
