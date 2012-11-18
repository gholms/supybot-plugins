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

import base64
import json
import re
import urllib2
from urlparse import urljoin

class SimpleJira(callbacks.Plugin):
    """Add the help for "@plugin help SimpleJira" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        super(SimpleJira, self).__init__(irc)

    def __send_request(self, relative_uri, data=None, method=None):
        '''
        Build a request for a location relative to JIRA's base URI, then send
        it and return the response.

        For now we assume data, if supplied, is always JSON.

        Don't forget to handle HTTPErrors.
        '''

        headers = {'Content-Type': 'application/json'}
        if self.registryValue('username') and self.registryValue('password'):
            auth = base64.encodestring(self.registryValue('username') + ':' +
                                       self.registryValue('password'))
            auth = auth.strip('\n')
            headers['Authorization'] = 'Basic ' + auth
        uri     = urljoin(self.registryValue('uri'), relative_uri)
        request = urllib2.Request(uri, data=data, headers=headers)

        if method is not None:
            # HACK
            request.get_method = lambda: method
        return urllib2.urlopen(request)

    def __handle_http_error(self, irc, err, errmsg):
        err_content = err.read()
        try:
            err_dict = json.loads(err_content)
        except ValueError:
            # The JSON failed to be decoded
            self.log.error(('JSON parsing failed for HTTP {0} response to '
                            'URI {1}, which was {2}').format(err.code,
                                    repr(err.geturl()), repr(err_content)))
            irc.error(errmsg)
            return
        err_bits = []
        for err_msg in err_dict.get('errorMessages', []):
            if err_msg.lower() != 'login required':
                # Might as well be a little paranoid / less noisy
                err_bits.append(err_msg)
        if len(err_bits) > 0:
            irc.error('  '.join(err_bits))
        else:
            irc.error(errmsg)

    def getissue(self, irc, msg, args, issueid):
        '''<id>

        Display information about an issue in JIRA along with a link to
        it on the web.
        '''
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            self.log.debug('SimpleJira is disabled in this channel; skipping')
            return
        if not check_issueid(issueid):
            irc.errorInvalid('issue ID', issueid)
            return

        try:
            response = self.__send_request('rest/api/2/issue/{0}'.format(
                    issueid.upper()))
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to retrieve issue data')
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
            cf_info = issue['fields'].get(cf_name)
            if (isinstance(cf_info, dict) and
                cf_info.get('value', '').lower() == 'yes'):
                # (This space for rent)
                issue_flags.append('security')

        # That's it for issue flags
        if issue_flags:
            msg_bits.append('(' + ', '.join(issue_flags) + ')')
        msg_bits[-1] += ':'

        # Summary
        msg_bits.append(issue['fields']['summary'] or '(no summary)')

        # Web URL
        msg_bits.append('-')
        msg_bits.append(urljoin(self.registryValue('uri'),
                                                   'browse/' + issue['key']))

        irc.reply(' '.join(msg_bits))

    getissue = wrap(getissue, ['somethingWithoutSpaces'])

    def assign(self, irc, msg, args, issueid, assignee, actor):
        '''<issue> to <assignee>

        Assign a JIRA issue to someone.  Use that person's JIRA account name.
        '''
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            self.log.debug('SimpleJira is disabled in this channel; skipping')
            return
        if not check_issueid(issueid):
            irc.errorInvalid('issue ID', issueid)
            return

        # First set the new assignee
        path = 'rest/api/2/issue/{0}/assignee'.format(issueid.upper())
        data = {'name': assignee}
        try:
            response = self.__send_request(path, json.dumps(data),
                                           method='PUT')
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to set issue assignee')
            return
        response.read()  # empty the buffer

        # Then say who actually did this assignment.
        path = 'rest/api/2/issue/{0}/comment'.format(issueid.upper())
        data = {'body': 'Assigned to {0} by {1}'.format(assignee, actor.name)}
        try:
            response = self.__send_request(path, json.dumps(data))
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to set issue assignee')
            return
        response.read()  # empty the buffer

        irc.replySuccess()

    assign = wrap(assign, ['somethingWithoutSpaces',  # issue to assign
                           'to',                      # Yay for English!
                           'somethingWithoutSpaces',  # assignee
                           'user',  # caller must be registered with the bot
                           ('checkCapability', 'jirawrite')])


def check_issueid(issueid):
    if re.match('[A-Za-z]{2,}-[0-9]+$', issueid):
        return True
    else:
        return False


Class = SimpleJira
