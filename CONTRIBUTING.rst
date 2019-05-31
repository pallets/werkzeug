How to contribute to Werkzeug
=============================

Thank you for considering contributing to Werkzeug!


Support questions
-----------------

Please, don't use the issue tracker for this. Use one of the following
resources for questions about your own code:

- The IRC channel ``#pocoo`` on FreeNode.
- The IRC channel ``#python`` on FreeNode for more general questions.
- The mailing list flask@python.org for long term discussion or larger
  issues.
- Ask on `Stack Overflow`_. Search with Google first using:
  ``site:stackoverflow.com werkzeug {search term, exception message, etc.}``.
  Be sure to include a `minimal, complete, and verifiable example`_.


Reporting issues
----------------

- Describe what you expected to happen.
- If possible, include a `minimal, complete, and verifiable example`_ to
  help us identify the issue. This also helps check that the issue is
  not with your own code.
- Describe what actually happened. Include the full traceback if there
  was an exception.
- List your Python and Werkzeug versions. If possible, check if
  this issue is already fixed in the repository.


Submitting patches
------------------

- Include tests if your patch is supposed to solve a bug, and explain
  clearly under which circumstances the bug happens. Make sure the test
  fails without your patch.
- Follow the `PEP8`_ style guide.


First time setup
~~~~~~~~~~~~~~~~

- Download and install the `latest version of git`_.
- Configure git with your `username`_ and `email`_::

        git config --global user.name 'your name'
        git config --global user.email 'your email'

- Make sure you have a `GitHub account`_.
- Fork Werkzeug to your GitHub account by clicking the `Fork`_ button.
- `Clone`_ your GitHub fork locally::

        git clone https://github.com/{username}/werkzeug
        cd werkzeug

- Add the main repository as a remote to update later::

        git remote add pallets https://github.com/pallets/werkzeug
        git fetch pallets

- Create a virtualenv::

        python3 -m venv env
        . venv/bin/activate
        # or "venv\Scripts\activate" on Windows

- Install Werkzeug in editable mode with development dependencies::

        pip install -e ".[dev]"


Start coding
~~~~~~~~~~~~

- Create a branch to identify the issue you would like to work on (e.g.
  ``2287-dry-test-suite``)
- Using your favorite editor, make your changes, `committing as you go`_.
- Follow the `PEP8`_ style guide.
- Include tests that cover any code changes you make. Make sure the test
  fails without your patch. Run the tests as described below.
- Push your commits to GitHub and `create a pull request`_.
- Celebrate 🎉


Running the tests
~~~~~~~~~~~~~~~~~

Run the basic test suite with::

    pytest

This only runs the tests for the current environment. Whether this is
relevant depends on which part of Werkzeug you're working on. Travis-CI
will run the full suite when you submit your pull request.

The full test suite takes a long time to run because it tests multiple
combinations of Python and dependencies. You need to have all supported
CPython and PyPy versions installed to run all of the environments. ::

    tox


Running test coverage
~~~~~~~~~~~~~~~~~~~~~

Generating a report of lines that do not have test coverage can indicate
where to start contributing. Run ``pytest`` using ``coverage`` and
generate a report on the terminal and as an interactive HTML document::

    coverage run -m pytest
    coverage report
    coverage html
    # then open htmlcov/index.html

Read more about `coverage`_.

Running the full test suite with ``tox`` will combine the coverage
reports from all runs.


.. _Stack Overflow: https://stackoverflow.com/questions/tagged/werkzeug?sort=linked
.. _minimal, complete, and verifiable example: https://stackoverflow.com/help/mcve
.. _GitHub account: https://github.com/join
.. _latest version of git: https://git-scm.com/downloads
.. _username: https://help.github.com/articles/setting-your-username-in-git/
.. _email: https://help.github.com/articles/setting-your-email-in-git/
.. _Fork: https://github.com/pallets/werkzeug/pull/2305#fork-destination-box
.. _Clone: https://help.github.com/articles/fork-a-repo/#step-2-create-a-local-clone-of-your-fork
.. _committing as you go: https://dont-be-afraid-to-commit.readthedocs.io/en/latest/git/commandlinegit.html#commit-your-changes
.. _PEP8: https://pep8.org/
.. _create a pull request: https://help.github.com/articles/creating-a-pull-request/
.. _coverage: https://coverage.readthedocs.io
