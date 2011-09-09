# -*- coding: utf-8 -*-
"""
    werkzeug.testsuite.utils
    ~~~~~~~~~~~~~~~~~~~~~~~~

    General utilities.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import unittest

from werkzeug.testsuite import WerkzeugTestCase

from werkzeug import utils


class GeneralUtilityTestCase(WerkzeugTestCase):

    def test_redirect(self):
        resp = utils.redirect(u'/füübär')
        assert '/f%C3%BC%C3%BCb%C3%A4r' in resp.data
        assert resp.headers['Location'] == '/f%C3%BC%C3%BCb%C3%A4r'
        assert resp.status_code == 302

        resp = utils.redirect(u'http://☃.net/', 307)
        assert 'http://xn--n3h.net/' in resp.data
        assert resp.headers['Location'] == 'http://xn--n3h.net/'
        assert resp.status_code == 307

        resp = utils.redirect('http://example.com/', 305)
        assert resp.headers['Location'] == 'http://example.com/'
        assert resp.status_code == 305


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(GeneralUtilityTestCase))
    return suite
