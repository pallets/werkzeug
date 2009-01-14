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
	werkzeug \
	tests \
	tests/contrib

TEST_OPTIONS = \
	-v \
	--with-doctest \
	-e '^test_app'

documentation:
	@(cd docs; python ./generate.py)

test:
	@(nosetests $(TEST_OPTIONS) $(TESTS))
