###
# Copyright (c) 2008, Bryan Petty
# All rights reserved.
#
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

import docset, time

class Doxygen(callbacks.Plugin):
    """This plugin provides quick API reference lookup. Use the "describe"
    command for class and function lookups."""

    def __init__(self, irc):
        self.__parent = super(Doxygen, self)
        self.__parent.__init__(irc)
        self.docs_loaded = False

    def check_version(self, version):
        """Checks if the given version of docs is loaded, and available."""
        # TODO
        return False


    version_context = getopts( { 'version':
        commalist('somethingWithoutSpaces') } )


    def doxyload(self, irc, msg, args, api, name):
        """<api> [<name>]

        Loads the Doxygen XML docs located in the given folder (api) in the
        doxygen-xml folder."""

        try:
            ts = time.time()
            self.docs = docset.DocSet(api)
            self.docs_loaded = True
            irc.reply("%d classes and %d methods loaded in %.2f seconds." %
                      (len(self.docs.classes), self.docs.method_count, time.time() - ts))
        except IOError:
            irc.error("Doxygen XML not found.")

    doxyload = wrap( doxyload, ['admin', 'filename', optional('text')] )


    def describe(self, irc, msg, args, version, api_class, api_function):
        """<method> | <class> [<method>]

        Gives a description of the class if given, or the syntax and
        description of the method if specified."""

        if not self.docs_loaded:
            irc.error("Doxygen XML has not been loaded.")
            return

        if not api_function and api_class.find('::') is not -1:
            api_function = api_class[api_class.rfind('::') + 2:]
            api_class = api_class[:api_class.rfind('::')]

        if api_function:
            reply = self.docs.get_method_desc(api_function, api_class)
            if reply is None:
                irc.error("Method not found in the given class or " +
                          "anywhere else.")
            else:
                [irc.reply(msg.encode('utf-8')) for msg in reply]
        else:
            reply = self.docs.get_class_desc(api_class)
            if reply is None:
                reply = self.docs.get_method_desc(api_class)
                if reply is None:
                    irc.error("Class or method not found.")
                else:
                    [irc.reply(msg.encode('utf-8')) for msg in reply]
            else:
                [irc.reply(msg.encode('utf-8')) for msg in reply]

    describe = wrap( describe, [version_context,
                                optional('somethingWithoutSpaces'),
                                optional('somethingWithoutSpaces')] )


Class = Doxygen

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
