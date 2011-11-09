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
from supybot.i18n import PluginInternationalization, internationalizeDocstring

import json
import urllib2
from urlparse import urljoin

_ = PluginInternationalization('Redmine')

@internationalizeDocstring
class Redmine(callbacks.Plugin):
    """Add the help for "@plugin help Redmine" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        super(self.__class__, self).__init__(irc)

    def getissue(self, irc, msg, args, issueno):
        """<id>

        Display information about an issue in Redmind along with a link to
        it on the web.
        """
        base_uri = self.registryValue('uri')
        rest_uri = urljoin(base_uri, 'issues/{0}.json'.format(issueno))
        try:
            response = urllib2.urlopen(rest_uri)
            response_content = response.read()
            response_json = json.loads(response_content)
        except urllib2.HTTPError as e:
            if str(e.code).startswith('4'):
                irc.error('issue {0} does not exist.'.format(issueno))
            else:
                self.log.error('GET on URI {uri} yielded HTTP {code} {msg}'
                               .format(uri=rest_uri, code=e.code, msg=e.msg))
                irc.error('failed to retrieve issue data')
            return
        except ValueError:
            self.log.error('Response from server is not JSON: ' + response_content)
            irc.error('failed to retrieve issue data')
            return
        if 'issue' in response_json:
            issue = response_json['issue']
        else:
            self.log.error("Response lacks an 'issue' key: " + response_content)
            irc.error('failed to retrieve issue data')
            return

        msg_bits = ['Issue']
        issue_flags = []
        msg_bits.append(str(issueno))
        if issue.get('status'):
            issue_flags.append(issue['status']['name'])
        if issue_flags:
            msg_bits.append('(' + ', '.join(issue_flags) + ')')
        msg_bits[-1] += ':'
        msg_bits.append(issue.get('subject', '(no subject)'))
        msg_bits.append('-')
        msg_bits.append(urljoin(base_uri, 'issues/{0}'.format(issueno)))
        irc.reply(' '.join(msg_bits))

    getissue = wrap(getissue, ['positiveInt'])

Class = Redmine
