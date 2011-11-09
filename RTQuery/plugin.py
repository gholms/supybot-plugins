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

import cookielib
import urllib
import urllib2
from urlparse import urljoin

class RTError(Exception):
    def __init__(self, value):
        self.value = value

class RTQuery(callbacks.Plugin):
    """Add the help for "@plugin help RTQuery" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        super(RTQuery, self).__init__(irc)

    def getticket(self, irc, msg, args, ticketno):
        """<id>

        Display information about a ticket in RT along with a link to
        it on the web.
        """
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            return
        base_uri = self.registryValue('uri')
        rest_uri = urljoin(base_uri, "REST/1.0/ticket/{0}".format(ticketno))
        if self.registryValue('authtype').lower() == 'basic':
            auth_handler = urllib2.HTTPBasicAuthHandler()
            auth_handler.add_password(self.registryValue('authRealm'),
                                      self.registryValue('uri'),
                                      self.registryValue('username'),
                                      self.registryValue('password'))
            opener = urllib2.build_opener(auth_handler)
            login  = urllib2.Request(rest_uri)
        elif self.registryValue('authtype').lower() == 'builtin':
            cjar   = cookielib.CookieJar()
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cjar))
            ldata  = urllib.urlencode({'user': self.registryValue('username'),
                                       'pass': self.registryValue('password')})
            login  = urllib2.Request(rest_uri, ldata)
        else:
            self.log.error('Unknown authType "{0}"'.format(
                    self.registryValue('authtype')))
            irc.errorInvalid('authType', self.registryValue('authtype'))
            return
        try:
            response = opener.open(login)
            tkt_attrs = self.__parse_rt_response(response)
        except urllib2.HTTPError as e:
            self.log.error('GET on URI {uri} yielded HTTP {code} {msg}'.format(
                    uri=rest_uri, code=e.code, msg=e.msg))
            irc.error('failed to retrieve ticket data')
            return
        except RTError as e:
            irc.error(e.value)
            return

        # The "id" field for a ticket looks like "ticket/123"
        real_tkt_id = tkt_attrs['id'].split('/')[1]

        msg_bits = ['Ticket']
        tkt_flags = []
        if str(ticketno) != real_tkt_id:
            msg_bits.append('*' + real_tkt_id)
        else:
            msg_bits.append(real_tkt_id)
        if tkt_attrs.get('Status'):
            tkt_flags.append(tkt_attrs['Status'])
        if tkt_attrs.get('CF.{Security}', '').lower() == 'yes':
            tkt_flags.append('security')
        if tkt_attrs.get('CF.{Security Threat}'):
            tkt_flags.append('threat=' + tkt_attrs['CF.{Security Threat}'])
        if tkt_flags:
            msg_bits.append('(' + ', '.join(tkt_flags) + ')')
        msg_bits[-1] += ':'
        msg_bits.append(tkt_attrs.get('Subject', '(no subject)'))
        msg_bits.append('-')
        msg_bits.append(urljoin(base_uri,
                'Ticket/Display.html?id={0}'.format(real_tkt_id)))
        irc.reply(' '.join(msg_bits))

    getticket = wrap(getticket, ['positiveInt'])


    def __parse_rt_response(self, response):
        attrs = {}
        for line in response.readlines():
            if line.startswith('RT/'):
                # RT puts its real response codes at the top of the response
                # content like so:  "RT/3.8.8 200 Ok"
                try:
                    (svr, code, msg) = line.strip().split(None, 2)
                    if code.startswith('4') or code.startswith('5'):
                        raise urllib2.HTTPError(response.geturl(), code, msg,
                                                None, None)
                except ValueError:
                    # Not enough elements; skip it
                    pass
            elif line.startswith('#'):
                # RT's error messages appear after octothorpes like this:
                # "# Ticket 0 does not exist."
                raise RTError(line.strip().split('#', 1)[1].strip())
            elif ':' in line:
                # Key: value pair
                (key, val) = line.split(':', 1)
                attrs[key.strip()] = val.strip()
        return attrs

Class = RTQuery
