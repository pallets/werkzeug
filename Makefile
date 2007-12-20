#
# Werkzeug Makefile
# ~~~~~~~~~~~~~~~~~
#
# Shortcuts for various tasks.
#
# :copyright: 2007 by Armin Ronacher.
# :license: BSD, see LICENSE for more details.
#

documentation:
	@(cd docs; python ./generate.py)

test:
	@(cd tests; py.test $(TESTS))
