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

IFACE_NUMBER_HEADING = "Port"
IFACE_TRUNK_HEADING = "Trunk"
IFACE_NAME_HEADING = "Beskrivning"
VLAN_HEADING = "VLAN-konfiguration (T=taggad, U=otaggad)"
COLLAPSE = True
TABLEWIDTH = True

from sys import stdin
from itertools import chain, zip_longest
import re

def ifkey(if_number):
    m = re.match(r"^([A-Za-z]*)(\d*)$", if_number)
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
        m = re.match(r"([A-Za-z]*)(\d+)-\1(\d+)", if_number_range)
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
        self.trunk = None

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
            (r'^\s+name "?(?P<vlan_name>.+?)"?$', self.set_name),
            (r'^\s+untagged (?P<if_numbers>\w(?:[\w,-]*\w))$', self.add_untagged),
            (r'^\s+tagged (?P<if_numbers>\w(?:[\w,-]*\w))$', self.add_tagged)
        ]

    def set_name(self, vlan_name):
        self.name = vlan_name

    def add_untagged(self, if_numbers):
        self.untagged.add_if_numbers(if_numbers)

    def add_tagged(self, if_numbers):
        self.tagged.add_if_numbers(if_numbers)

class ProcurveTrunk(object):
    def __init__(self):
        self.trunkname = None
        self.members = ProcurveInterfaceCollection()

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
            (r'^hostname "?(?P<hostname>.+?)"?$', self._set_hostname),
            (r'^trunk (?P<members>\w(?:[\w,-]*\w)) (?P<trunkname>Trk\d+)', self._set_trunk),
            (r'^\s*exit$', self._exit_context)
        ]

    def _enter_interface_context(self, if_number):
        iface = self._get_iface_by_number(if_number)
        self._context_regexes = iface._get_regexes()

    def _enter_vlan_context(self, vlan_number):
        vlan = self._get_vlan_by_number(vlan_number)
        self._context_regexes = vlan._get_regexes()

    def _set_hostname(self, hostname):
        self.hostname = hostname

    def _set_trunk(self, trunkname, members):
        t = ProcurveTrunk()
        t.trunkname = trunkname
        t.members.add_if_number_range(members)
        for member in t.members.interfaces:
            self._get_iface_by_number(member).trunk = t

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
        vlan_numbers.sort(key=int)
        return map(self._get_vlan_by_number, vlan_numbers)

    def __init__(self, fp):
        self._interfaces = {}
        self._vlans = {}
        self._context_regexes = []
        self.hostname = ''
        _global_regexes = self._get_regexes()
        for line in fp:
            for regex, func in chain(self._context_regexes, _global_regexes):
                m = re.match(regex, line)
                if m:
                    func(**m.groupdict())

def fmt_row(column_data, column_widths, separator='|'):
    row = '%s' % separator
    for d, w in zip(column_data, column_widths):
        row += ' %s %s' % (d.ljust(w), separator)
    return row

def collapse_rows(data_rows):
    last_row = reference_row = data_rows[0]
    for current_row in data_rows[1:]+[[]]:
        if current_row[1:] != reference_row[1:]:
            first, last = reference_row[0], last_row[0]
            if first == last:
                yield reference_row
            else:
                yield ["%s-%s" % (first, last)] + reference_row[1:]
            reference_row = current_row
        last_row = current_row

def main():
    cfg = ProcurveConfig(stdin)
    vlans = list(cfg.get_all_vlans())
    ifaces = list(cfg.get_all_interfaces())
    vlan_count = len(vlans)

    heading_row = [IFACE_NUMBER_HEADING, IFACE_TRUNK_HEADING, IFACE_NAME_HEADING] + [str(vlan.number) for vlan in vlans]

    data_rows = []
    for iface in ifaces:
        if iface.number.startswith('Trk'):
            continue
        if iface.trunk:
            if_num = iface.trunk.trunkname
            data = [iface.number, if_num, iface.name or '']
        else:
            if_num = iface.number
            data = [iface.number, '', iface.name or '']
        for vlan in vlans:
            if if_num in vlan.tagged.interfaces:
                data += ['T']
            elif if_num in vlan.untagged.interfaces:
                data += ['U']
            else:
                data += ['']
        data_rows += [data]
    if COLLAPSE:
        data_rows = list(collapse_rows(data_rows))

    # Get maximum length of data in each column
    column_widths = [max(len(row[i]) for row in chain([heading_row], data_rows)) for i in range(len(heading_row))]

    if TABLEWIDTH:
        print("|< 100% - -" + vlan_count*" 3em" + " >|")
    print("^ %s ^^^ %s %s" % (cfg.hostname, VLAN_HEADING, vlan_count * '^'))
    print(fmt_row(heading_row, column_widths, '^'))
    for data_row in data_rows:
        print(fmt_row(data_row, column_widths))

if __name__ == '__main__':
    main()
