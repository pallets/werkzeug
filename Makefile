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

documentation:
	@(cd docs; python ./generate.py)

test:
	@(nosetests -v $(TESTS))
