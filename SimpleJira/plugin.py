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
        for err_key, err_val in err_dict.get('errors', {}).iteritems():
            err_bits.append('{0}: {1}'.format(err_key, err_val))
        if len(err_bits) > 0:
            irc.error('  '.join(err_bits))
        else:
            irc.error(errmsg)

    def getissue(self, irc, msg, args, issuekey):
        '''<issue>

        Display information about an issue in JIRA along with a link to
        it on the web.
        '''
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            self.log.debug('SimpleJira is disabled in this channel; skipping')
            return
        if not check_issuekey(issuekey):
            irc.errorInvalid('issue key', issuekey)
            return

        try:
            response = self.__send_request('rest/api/2/issue/{0}'.format(
                    issuekey.upper()))
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
            issue_flags.append('{0} ({1})'.format(status, resolution['name']))
        else:
            issue_flags.append(status)

        # 'blocker' priority
        if issue['fields']['priority']['name'] == 'Blocker':
            issue_flags.append('Blocker')

        # 'security' boolean custom field
        security_field_id = self.registryValue('securityFieldId')
        if security_field_id > 0:
            cf_name = 'customfield_' + str(security_field_id)
            cf_info = issue['fields'].get(cf_name)
            if (isinstance(cf_info, dict) and
                cf_info.get('value', '').lower() == 'yes'):
                # (This space for rent)
                issue_flags.append('Security')

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

    def assign(self, irc, msg, args, issuekey, assignee, actor, comment):
        '''<issue> to <assignee> [comment ...]

        Assign a JIRA issue to someone.  Use that person's JIRA account name.
        '''
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            self.log.debug('SimpleJira is disabled in this channel; skipping')
            return
        if not check_issuekey(issuekey):
            irc.errorInvalid('issue key', issuekey)
            return

        # Assign the issue...
        path = 'rest/api/2/issue/{0}/assignee'.format(issuekey.upper())
        data = {'name': assignee}
        try:
            response = self.__send_request(path, json.dumps(data),
                                           method='PUT')
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to set issue assignee')
            return
        response.read()  # empty the buffer

        # ...then log who did it.
        path = 'rest/api/2/issue/{0}/comment'.format(issuekey.upper())
        data = {'body': 'Assigned to {0} by {1}'.format(assignee, actor.name)}
        if comment is not None:
            data['body'] += '\n\n' + comment
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
                           ('checkCapability', 'jirawrite'),
                           optional('text')])

    def transition(self, irc, msg, args, issuekey, transid, actor, opts,
                   comment):
        '''<issue> <trans_id> [--resolution <resolution>] [comment ...]

        Perform a transition on a JIRA issue.
        '''
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            self.log.debug('SimpleJira is disabled in this channel; skipping')
            return
        if not check_issuekey(issuekey):
            irc.errorInvalid('issue key', issuekey)
            return

        # Perform the transition...
        path = 'rest/api/2/issue/{0}/transitions'.format(issuekey.upper())
        data = {'transition': {'id': transid}}
        resolution = dict(opts).get('resolution')
        if resolution:
            # Note that JIRA will complain if the transition doesn't actually
            # take a resolution.
            data['fields'] = {'resolution': {'name': resolution}}
        try:
            response = self.__send_request(path, json.dumps(data))
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to transition issue')
            return
        response.read()  # empty the buffer

        # ...then log who did it.
        path = 'rest/api/2/issue/{0}/comment'.format(issuekey.upper())
        data = {'body': 'Status updated by {0}'.format(actor.name)}
        if comment is not None:
            data['body'] += '\n\n' + comment
        try:
            response = self.__send_request(path, json.dumps(data))
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to transition issue')
            return
        response.read()  # empty the buffer

        irc.replySuccess()

    transition = wrap(transition,
                      ['somethingWithoutSpaces',  # issue to transition
                       'positiveInt',  # transition ID
                       'user',         # caller must be registered with the bot
                       getopts({'resolution': 'something'}),
                       ('checkCapability', 'jirawrite'),
                       optional('text')])

    def comment(self, irc, msg, args, issuekey, actor, comment):
        '''<issue> <comment>

        Add a comment to a JIRA issue.
        '''
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            self.log.debug('SimpleJira is disabled in this channel; skipping')
            return
        if not check_issuekey(issuekey):
            irc.errorInvalid('issue key', issuekey)
            return

        path = 'rest/api/2/issue/{0}/comment'.format(issuekey.upper())
        data = {'body': 'Comment from {0}:\n\n{1}'.format(actor.name, comment)}
        try:
            response = self.__send_request(path, json.dumps(data))
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to comment on issue')
            return
        response.read()  # empty the buffer

        irc.replySuccess()

    comment = wrap(comment, ['somethingWithoutSpaces',  # issue to transition
                             'user',  # caller must be registered with the bot
                             ('checkCapability', 'jirawrite'),
                             'text'])

    def setfield(self, irc, msg, args, actor, issuekey, field, raw_value):
        '''<issue> <field> <value>

        Set a field of a JIRA issue.  The value given can be either a string
        or a comma-delimited list of strings surrounded by parentheses.
        '''
        # We actually make a ton of assumptions here (most notably that we need
        # to use 'name' as the key for each field value.
        channel = msg.args[0]
        if not self.registryValue('enabled', channel):
            self.log.debug('SimpleJira is disabled in this channel; skipping')
            return
        if not check_issuekey(issuekey):
            irc.errorInvalid('issue key', issuekey)
            return

        # Set the field...
        path = 'rest/api/2/issue/{0}'.format(issuekey.upper())
        if raw_value.startswith('(') and raw_value.endswith(')'):
            values = raw_value.strip('()').split(',')
            values_dict = [{'name': value.strip()} for value in values]
            data = {'fields': {field: values_dict}}
        else:
            data = {'fields': {field: {'name': raw_value}}}
        try:
            response = self.__send_request(path, json.dumps(data),
                                           method='PUT')
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to update issue')
            return
        response.read()  # empty the buffer

        # ...then log who did it.
        path = 'rest/api/2/issue/{0}/comment'.format(issuekey.upper())
        data = {'body': 'Field updated by {0}'.format(actor.name)}
        try:
            response = self.__send_request(path, json.dumps(data))
        except urllib2.HTTPError as err:
            self.__handle_http_error(irc, err, 'Failed to update issue')
            return
        response.read()  # empty the buffer

        irc.replySuccess()

    setfield = wrap(setfield, ['user',  # caller must be registered
                               'somethingWithoutSpaces',  # issue
                               'somethingWithoutSpaces',  # field
                               'text',                    # value
                               ('checkCapability', 'jirawrite')])



def check_issuekey(issuekey):
    if re.match('[A-Za-z]{2,}-[0-9]+$', issuekey):
        return True
    else:
        return False


Class = SimpleJira
