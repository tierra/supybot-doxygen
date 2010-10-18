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

import os.path
from objectify import *
from types import StringTypes, FunctionType
import supybot.ircutils as utils

# Text to use to indicate a paragraph break.
para_indicator = ' ... '

# List of XML tags that get replaced or ignored entirely.
bad_tags = {
    'programlisting': 'code example omitted',
    'preformatted'  : 'content ommitted',
    'orderedlist'   : 'list ommitted',
    'itemizedlist'  : 'list ommitted',
    'variablelist'  : 'variable list ommitted',
    'table'         : 'table ommitted',
    'image'         : 'image ommitted',
    'dotfile'       : 'graph ommitted',
    'htmlonly'      : ''
}

# List of paragraphs with the given headings to strip from output.
para_stripped = [
    'Styles',
    'Events emitted by this class',
    'Events using this class'
]

def get_xml_path(api, xml_file):
    import docset
    path = str(docset).split()[3][1:-2]
    path = os.path.dirname(os.path.realpath(path))
    return os.path.join(path, 'doxygen-xml', api, xml_file)

class DocSet:
    """Provides access to a single version of Doxygen docs."""

    def __init__(self, api):
        self.api = api
        self.classes = {}
        self.methods = {}
        self.method_count = 0
        # Load the main index with all compounds
        self.index = make_instance(get_xml_path(api, 'index.xml'))
        # Cache all classes and class methods
        for cn in [n for n in self.index.compound if n.kind == 'class']:
            class_methods = {}
            try:
                for mn in [x for x in cn.member if x.kind == 'function']:
                    class_methods[mn.refid] = mn.name.PCDATA
                self.method_count += len(class_methods)
            except AttributeError: pass
            class_name = cn.name.PCDATA.replace(' ', '')
            if class_name[-3:] == '<T>':
                self.classes[cn.refid] = (class_name[0:-3], class_methods)
            else:
                self.classes[cn.refid] = (class_name, class_methods)
        # Cache all global methods
        for cn in [n for n in self.index.compound
                   if n.kind == 'file' or n.kind == 'group']:
            try:
                for mn in [i for i in cn.member if i.kind == 'function']:
                    if mn.refid not in self.methods:
                        self.methods[mn.refid] = mn.name.PCDATA
            except: pass
        self.method_count += len(self.methods)


    def get_class_desc(self, keyword):
        class_info = [(refid, name) for refid, (name, methods) in
                      self.classes.items() if name == keyword]
        if not class_info:
            return None

        (refid, name) = class_info[0]
        docs = make_instance(get_xml_path(self.api, refid + '.xml'))

        details = [utils.bold(name)]
        try: details += ['[#include "%s"]' % docs.compounddef.includes.PCDATA]
        except: pass
        try: details += ['(Super-classes: %s)' %
            ', '.join([utils.bold(c.PCDATA) for c in docs.compounddef.basecompoundref])]
        except: pass
        try: details += ['(Sub-classes: %s)' %
            ', '.join([utils.bold(c.PCDATA) for c in docs.compounddef.derivedcompoundref])]
        except: pass
        details = ' '.join(details)

        try: brief = cleaner(docs.compounddef.briefdescription).reply
        except: brief = ''
        try: detailed = cleaner(docs.compounddef.detaileddescription).reply
        except: detailed = ''
        full = '%s %s' % (brief, detailed)
        full = full.strip()
        if full is '': full = '%s has no description.' % name

        return [details, full]


    def _method_reply(self, refid, signature_only = False):
        '''Returns a reply describing the given method.
        
        This is an internal class method meant to be used when the actual
        method being printed has already been found.'''

        filename = refid.rsplit('_', 1)[0]
        docs = make_instance(get_xml_path(self.api, filename + '.xml'))
        section_nodes = docs.compounddef.sectiondef
        md = [n for m in [n.memberdef for n in section_nodes]
              for n in m if n.id == refid][0]
        overloads = [n for m in [n.memberdef for n in section_nodes]
                     for n in m if n.id != refid
                     and n.name.PCDATA == md.name.PCDATA]

        details = [utils.bold(md.definition.PCDATA + md.argsstring.PCDATA)]
        for method in overloads:
            details += [utils.bold(method.definition.PCDATA +
                                   method.argsstring.PCDATA)]

        try: brief = cleaner(md.briefdescription).reply
        except: brief = ''
        try: detailed = cleaner(md.detaileddescription).reply
        except: detailed = ''
        full = '%s %s' % (brief, detailed)
        full = full.strip()
        if full is '': full = '%s has no description.' % md.name.PCDATA

        if signature_only: return details
        return details + [full]


    def _search_for_method(self, name, search_global_scope = False):
        '''Looks for the given method in all classes.

        This is an internal class method meant to be used only when a search
        for the given class has yielded no results in the global scope if no
        scope was defined, or when there are no results in the given class when
        scope is defined and no results in super-classes.'''

        methods_found = {}

        if search_global_scope:
            method_info = [(k, v) for k, v in self.methods.items()
                           if v == name]
            if method_info:
                # We only need the first, overloads will be handled later
                methods_found[method_info[0][0]] = (method_info[0][1], '')

        classes = [(c_name, methods) for refid, (c_name, methods)
                   in self.classes.items() if name in methods.values()]
        for (c_name, methods) in classes:
            matches = [(refid, m_name) for (refid, m_name) in
                       methods.items() if m_name == name]
            if matches:
                # We only need the first, overloads will be handled later
                methods_found[matches[0][0]] = (matches[0][1], c_name)

        if len(methods_found) is 0:
            return None
        elif len(methods_found) is 1:
            for refid in methods_found.keys():
                return self._method_reply(refid)
        else:
            # Multiple sources found, just return a list of the methods.
            return [('%d methods found: ' % len(methods_found)) + ', '.join(
                    [(scope + '::' + name) for (name, scope)
                     in methods_found.values()])]


    def get_method_desc(self, identifier, scope = None):
        if scope is None:
            method_info = [refid for refid, name
                           in self.methods.items() if name == identifier]
            if method_info:
                return self._method_reply(method_info[0])
            else:
                return self._search_for_method(identifier)
        else:
            class_info = [methods for refid, (name, methods)
                          in self.classes.items() if name == scope
                          and identifier in methods.values()]
            if not class_info:
                # TODO: Try looking in base classes before falling back to
                # searching globally and in all classes as it does now.
                return self._search_for_method(identifier, True)

            refids = [refid for refid, name in class_info[0].items()
                      if name == identifier]
            return self._method_reply(refids[0])



class cleaner:

    def __init__(self, o):
        self.o = o
        content = self.scrape_content(o)
        while content[-1] == para_indicator or content[-1].strip() == '': content.pop()
        self.reply = ''.join(content).replace('\n', ' ').strip()

    def scrape_content(self, o):
        """Strip tags and return an array of the content."""
        stripped = []
        strip_next_node = False
        for node in content(o):
            if type(node) in StringTypes:
                stripped += [node]
                continue
            if strip_next_node:
                strip_next_node = False
                continue
            if tagname(node) == 'para':
                try:
                    if node.heading[0].PCDATA.strip() in para_stripped:
                        strip_next_node = True
                    continue
                except AttributeError: pass
            if tagname(node) in bad_tags.keys():
                if bad_tags[tagname(node)] is not '':
                    stripped += [' [ %s ] ' % bad_tags[tagname(node)]]
            elif self.has_handler(tagname(node)):
                handler = getattr(self, 'handle_' + tagname(node))
                stripped += handler(node)
            else:
                stripped += self.scrape_content(node)
                if tagname(node) == 'para': stripped += [para_indicator]
        return stripped

    def has_handler(self, name):
        try:
            if callable(getattr(self, 'handle_' + name)): return True
        except: pass
        return False

    def handle_nonbreakablespace(self, o):
        return [' ']

    def handle_simplesect(self, o):
        return [utils.bold(o.kind.capitalize()), ': '] + \
                self.scrape_content(o.para) + [para_indicator]

    def handle_verbatim(self, o):
        if o.PCDATA.find('\n') == -1:
            return ['"' + o.PCDATA + '"']
        else:
            return ['[ content ommitted ]']

    def handle_xrefsect(self, o):
        try:
            stripped = [utils.bold(o.xreftitle.PCDATA.capitalize()), ': ']
        except:
            stripped = []
        return stripped + self.scrape_content(o.xrefdescription)

    def handle_ref(self, o):
        return [utils.bold(o.PCDATA)]



# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
