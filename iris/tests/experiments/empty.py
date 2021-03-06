# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


from test_case import *


class test(base_test):

    def __init__(self, app):
        base_test.__init__(self, app)
        self.meta = 'This is an empty test case that does nothing'

    def run(self):
        """
        This is where your test logic goes.
        """
        assert_equal(self, 1, 1, 'test')
        assert_true(self, False, 'test')
        return
