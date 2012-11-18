###
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

import json
import re
import urllib
import urllib2
from urlparse import urljoin

class SimpleJira(callbacks.Plugin):
    """Add the help for "@plugin help SimpleJira" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        super(SimpleJira, self).__init__(irc)

    def getissue(self, irc, msg, args, issueid):
        '''<id>

        Display information about an issue in JIRA along with a link to
        it on the web.
        '''
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            return

        if not re.match('[A-Za-z]{2,}-[0-9]+$', issueid):
            irc.errorInvalid('issue ID', issueid)
            return

        base_uri = self.registryValue('uri')
        rest_uri = urljoin(base_uri, 'rest/api/2/issue/{0}'.format(
                           issueid.upper()))
        if self.registryValue('username') and self.registryValue('password'):
            passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passmgr.add_password(None, self.registryValue('uri'),
                                 self.registryValue('username'),
                                 self.registryValue('password'))
            auth_handler = urllib2.HTTPDigestAuthHandler(passmgr)
            opener = urllib2.build_opener(auth_handler)
        else:
            # Anonymous
            opener = urllib2.build_opener()
        login = urllib2.Request(rest_uri)

        try:
            response = opener.open(login)
        except urllib2.HTTPError as err:
            err_content = err.read()
            try:
                err_dict = json.loads(err_content)
            except ValueError:
                # The JSON failed to be decoded
                self.log.error(('JSON parsing failed for HTTP {0} response to '
                                'URI {1}, which was {2}').format(err.code,
                                        repr(rest_uri), repr(err_content)))
                irc.error('Failed to retrieve issue data')
                return
            err_bits = []
            for msg in err_dict.get('errorMessages', []):
                if msg.lower() != 'login required':
                    # Might as well be a little paranoid / less noisy
                    err_bits.append(msg)
            if len(err_bits) > 0:
                irc.error('  '.join(err_bits))
            else:
                irc.error('Failed to retrieve issue data')
            return
        try:
            issue = json.load(response)
        except ValueError:
            self.log.error(('JSON parsing failed for HTTP {0} response to '
                            'URI {1}').format(err.code, repr(rest_uri)))

        # Now create the output
        msg_bits = [issue['key']]
        issue_flags = []

        # status
        status     = issue['fields']['status']['name']
        resolution = issue['fields']['resolution']
        if resolution and status in ('Release Pending', 'Resolved', 'Closed'):
            issue_flags.append(status + '->' + resolution['name'])
        else:
            issue_flags.append(status)

        # 'blocker' priority
        if issue['fields']['priority']['name'] == 'Blocker':
            issue_flags.append('blocker')

        # 'security' boolean custom field
        security_field_id = self.registryValue('securityFieldId')
        if security_field_id > 0:
            cf_name = 'customfield_' + str(security_field_id)
            cf_value = issue['fields'].get(cf_name, {}).get('value', '')
            if cf_value.lower() == 'yes':
                issue_flags.append('security')

        # That's it for issue flags
        if issue_flags:
            msg_bits.append('(' + ', '.join(issue_flags) + ')')
        msg_bits[-1] += ':'

        # Summary
        msg_bits.append(issue['fields']['summary'] or '(no summary)')

        # Web URL
        msg_bits.append('-')
        msg_bits.append(urljoin(base_uri, 'browse/' + issue['key']))

        irc.reply(' '.join(msg_bits))

    getissue = wrap(getissue, ['somethingWithoutSpaces'])


Class = SimpleJira
