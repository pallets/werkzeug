#
# Werkzeug Makefile
# ~~~~~~~~~~~~~~~~~
#
# Shortcuts for various tasks.
#
# :copyright: (c) 2008 by the Werkzeug Team, see AUTHORS for more details.
# :license: BSD, see LICENSE for more details.
#

TESTS = \
	tests \
	tests/contrib

TEST_OPTIONS = \
	-v \
	-e '^test_app$$' #skip the test_app application object which is not a test

documentation:
	@(cd docs; make html)

test:
	@(nosetests $(TEST_OPTIONS) $(TESTS))

coverage:
	@(nosetests $(TEST_OPTIONS) --with-coverage --cover-package=werkzeug --cover-html --cover-html-dir=coverage_out $(TESTS))

doctest:
	@(cd docs; sphinx-build -b doctest . _build/doctest)
