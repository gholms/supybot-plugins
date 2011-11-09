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

import re
import urllib
from xml.etree import ElementTree

class GoogleWeather(callbacks.Plugin):
    """Add the help for "@plugin help GoogleWeather" here
    This should describe *how* to use this plugin."""
    threaded = True

    def weather(self, irc, msg, args, location):
        """[<location>]

        Display the current weather conditions in <location>."""
        if re.match(r"[\d\w\s',.-]+$", location, re.UNICODE):
            location = location.replace(' ', '+')
            url = ('http://www.google.com/ig/api?weather=' +
                   urllib.quote(location))
            root = ElementTree.parse(urllib.urlopen(url)).getroot()
            cond = root.find('weather/current_conditions/condition').get('data')
            temp = root.find('weather/current_conditions/temp_f').get('data') + ' F'
            wind = root.find('weather/current_conditions/wind_condition').get('data').replace('Wind:', 'wind')
            humidity = ' '.join(reversed(root.find('weather/current_conditions/humidity').get('data').replace('Humidity:', 'humidity').split()))
            place = root.find('weather/forecast_information/city').get('data')
            msg = ''
            msg1 = ' and '.join(filter(None, [cond, temp]))
            msg2 = ' and '.join(filter(None, [wind, humidity]))
            if msg1 and msg2:
                msg = msg1 + ' with ' + msg2
            if place:
                msg = msg + ' in ' + place
            if msg:
                irc.reply(msg)
            else:
                self.log.error('Failed to get weather data from Google for "{0}"'.format(location))
                irc.error("I can't seem to find that location.")
        else:
            self.log.error('Location "{0}" does not match expected regex'.format(location))
            irc.error("I can't seem to find that location.")

    weather = wrap(weather, [optional('text', default='Goleta, CA')])

Class = GoogleWeather
