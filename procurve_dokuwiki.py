# procurve_dokuwiki.py - Parses HP Procurve config files and makes DokuWiki tables
# https://github.com/pv2b/procurve_dokuwiki
#
# Copyright (c) 2017  Per von Zweigbergk <pvz@itassistans.se>
#
# MIT License
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from sys import stdin
from itertools import chain
import re

def ifkey(if_number):
    m = re.match(r"^([A-Z]*)(\d*)$", if_number)
    letter, number = m.groups()
    return letter, int(number)

class ProcurveInterfaceCollection():
    def __init__(self):
        self.interfaces = set()

    def add_if_numbers(self, if_numbers):
        for if_number_or_range in if_numbers.split(','):
            if '-' in if_number_or_range:
                self.add_if_number_range(if_number_or_range)
            else:
                self.add_if_number(if_number_or_range)

    def add_if_number_range(self, if_number_range):
        m = re.match(r"([A-Z]?)(\d+)-\1(\d+)", if_number_range)
        module, start, end = m.groups()
        start = int(start)
        end = int(end)
        for i in range(start, end+1):
            self.add_if_number("%s%d" % (module, i))

    def add_if_number(self, if_number):
        self.interfaces.add(if_number)

class ProcurveInterface(object):
    def __init__(self, number):
        self.number = number
        self.name = None

    def _get_regexes(self):
        return [
            (r'^\s+name "?(?P<if_name>.+?)"?$', self.set_name)
        ]

    def set_name(self, if_name):
        self.name = if_name

class ProcurveVlan(object):
    def __init__(self, number):
        self.number = number
        self.name = None
        self.untagged = ProcurveInterfaceCollection()
        self.tagged = ProcurveInterfaceCollection()

    def _get_regexes(self):
        return [
            (r'^\s+name "?(?P<vlan_name>.+)"?$', self.set_name),
            (r'^\s+untagged (?P<if_numbers>\w(?:[\w,-]*\w))?$', self.add_untagged),
            (r'^\s+tagged (?P<if_numbers>\w(?:[\w,-]*\w))?$', self.add_tagged)
        ]

    def set_name(self, vlan_name):
        self.name = vlan_name

    def add_untagged(self, if_numbers):
        self.untagged.add_if_numbers(if_numbers)

    def add_tagged(self, if_numbers):
        self.tagged.add_if_numbers(if_numbers)

class ProcurveConfig(object):
    def _get_iface_by_number(self, if_number):
        if if_number in self._interfaces:
            return self._interfaces[if_number]
        else:
            self._interfaces[if_number] = iface = ProcurveInterface(if_number)
            return iface

    def _get_vlan_by_number(self, vlan_number):
        if vlan_number in self._vlans:
            return self._vlans[vlan_number]
        else:
            self._vlans[vlan_number] = vlan = ProcurveVlan(vlan_number)
            return vlan

    def _get_regexes(self):
        return [
            (r'^interface (?P<if_number>\w+)$', self._enter_interface_context),
            (r'^vlan (?P<vlan_number>\d+)$', self._enter_vlan_context),
            (r'^\s*exit$', self._exit_context)
        ]

    def _enter_interface_context(self, if_number):
        iface = self._get_iface_by_number(if_number)
        self._context_regexes = iface._get_regexes()

    def _enter_vlan_context(self, vlan_number):
        vlan = self._get_vlan_by_number(vlan_number)
        self._context_regexes = vlan._get_regexes()

    def _exit_context(self):
        self._context_regexes = []

    def get_all_interfaces(self):
        all_interfaces = set()
        for k in self._interfaces.keys():
            all_interfaces.add(k)
        for vlan in self._vlans.values():
            for k in chain(vlan.untagged.interfaces, vlan.tagged.interfaces):
                all_interfaces.add(k)
        iface_numbers_sorted = sorted(all_interfaces, key=ifkey)
        return map(self._get_iface_by_number, iface_numbers_sorted)

    def get_all_vlans(self):
        vlan_numbers = list(self._vlans.keys())
        vlan_numbers.sort()
        return map(self._get_vlan_by_number, vlan_numbers)

    def __init__(self, fp):
        self._interfaces = {}
        self._vlans = {}
        self._context_regexes = []
        _global_regexes = self._get_regexes()
        for line in fp:
            for regex, func in chain(self._context_regexes, _global_regexes):
                m = re.match(regex, line)
                if m:
                    func(**m.groupdict())

def main():
    cfg = ProcurveConfig(stdin)
    vlans = list(cfg.get_all_vlans())
    ifaces = list(cfg.get_all_interfaces())
    vlan_count = len(vlans)

    IFACE_NUMBER_HEADING = "Port"
    IFACE_NAME_HEADING = "Beskrivning"
    VLAN_HEADING = "VLAN-konfiguration (T=taggad, U=otaggad)"

    iface_number_field_width = len(IFACE_NUMBER_HEADING)
    for iface in ifaces:
        if iface.number:
            iface_number_field_width = max(iface_number_field_width, len(iface.number))

    iface_name_field_width = len(IFACE_NAME_HEADING)
    for iface in ifaces:
        if iface.name:
            iface_name_field_width = max(iface_name_field_width, len(iface.name))

    vlan_heading_width = 6 * vlan_count - 2
    
    iface_name_heading_field_width = iface_name_field_width
    if vlan_heading_width < len(VLAN_HEADING):
        iface_name_heading_field_width -= len(VLAN_HEADING) - vlan_heading_width

    outline = "^ " + IFACE_NUMBER_HEADING.ljust(iface_number_field_width)
    outline += " ^ " + IFACE_NAME_HEADING.ljust(iface_name_heading_field_width)
    outline += " ^ " + VLAN_HEADING.ljust(vlan_heading_width) + " "
    outline += vlan_count * "^"
    print(outline)

    outline = "^ " + ":::".ljust(iface_number_field_width)
    outline += " ^ " + ":::".ljust(iface_name_field_width) + " ^"
    for vlan in vlans:
        outline += " %4s ^" % vlan.number
    print(outline)

    for iface in ifaces:
        number = iface.number or ''
        name = iface.name or ''
        outline = "| " + number.ljust(iface_number_field_width)
        outline += " | " + name.ljust(iface_name_field_width) + " |"
        for vlan in vlans:
            if iface.number in vlan.tagged.interfaces:
                outline += " T    |"
            elif iface.number in vlan.untagged.interfaces:
                outline += " U    |"
            else:
                outline += "      |"
        print(outline)

if __name__ == '__main__':
    main()
