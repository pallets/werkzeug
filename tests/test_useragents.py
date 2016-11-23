from __future__ import with_statement
from werkzeug.useragents import UserAgentParser


def test_useragentparser_checks_whole_word_for_platform():
    uap = UserAgentParser()
    uap_res = uap('Mozilla/5.0 (Linux; Android 4.4.4; Google Nexus 7' +
                  '2013 - 4.4.4 - API 19 - 1200x1920 Build/KTU84P)' +
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106'
                  'Crosswalk/21.51.546.7 Safari/537.36')
    assert uap_res == 'android'
