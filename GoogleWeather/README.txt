What is it?
===========

The RTQuery plugin allows Supybot to display ticket information from
an installation of Request Tracker (http://bestpractical.com/rt/).
It was originally created for Eucalyptus Systems.

Commands for RTQuery
====================

getticket:
    Displays information about a ticket in RT along with a link to it
    on the web.  Its sole argument is the id of the ticket to retrieve.
    The output has the following format:

        Ticket <id> (<flags>): <subject> - <uri>

    <id> is the ticket number.  If this number differs from the number
    you input because the ticket was involved in a merge then it will
    be preceded by a *.

    <flags> currently includes only the ticket's status, such as "new",
    "open", or "resolved".

    <summary> is the ticket's subject, or "(no subject)" if the subject
    is empty.

    <uri> is a link to the ticket on the web.

    Sample output:
        Ticket 3 (new): Traceback in test.py - https://www.example.com/rt3/Ticket/Display.html?id=3
        Ticket *443 (open): Failure with HTTPS - https://www.example.com/rt3/Ticket/Display.html?id=443
        Ticket 86 (deleted): (no subject) - https://www.example.com/rt3/Ticket/Display.html?id=86
        Error: Ticket 999999 does not exist.

Configuration variables
=======================

enable (channel-specific):

    Determines whether this plugin is enabled.  Note that enabling the
    plugin globally allows access to ticket data via private messages
    to the bot.  Default: False

uri:

    The top-level URI for the RT installation the bot should communicate
    with, such as "https://www.example.com/rt3".  This value must be set.

username (private):

    The username the bot should use to authenticate to RT.  This value
    must be set.

password (private):

    The password the bot should use to authenticate to RT.  This value
    must be set.

authType:

    The authentication method used by RT.  Valid values include:

        "builtin" - RT's built-in cookie-based authentication method
                    (default)
        "basic"   - HTTP basic authentication

    If you don't know what authType your RT instance uses, choose
    "builtin".

authRealm:

    The realm to use when authenticating to RT.  This is required when
    authType = "basic", in which case it must match the realm the web
    server uses for authenticating users to RT.  It is otherwise ignored.
