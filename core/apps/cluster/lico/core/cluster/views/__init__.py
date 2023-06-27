# Copyright 2015-2023 Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools
import re

from rest_framework.response import Response

from lico.core.contrib.views import APIView

from ..models import NodeGroup, Room
from ..serializers import RoomSerializer


class NodeEditorFixturesView(APIView):
    def get(self, request):
        data = {
            "groups": NodeGroup.objects.as_dict(inspect_related=True),
            "rooms": RoomSerializer(Room.objects.all(), many=True).data,
        }
        return Response(data)


class BadHostlist(Exception):
    pass


class HostlistMixin(object):
    # Configuration to guard against ridiculously long expanded lists
    MAX_SIZE = 100000

    def expand_hostlist(self, hostlist, allow_duplicates=False, sort=False):  # noqa
        """Expand a hostlist expression string to a Python list.

        Example: expand_hostlist("n[9-11],d[01-02]") ==>
                 ['n9', 'n10', 'n11', 'd01', 'd02']

        Unless allow_duplicates is true, duplicates will be purged
        from the results. If sort is true, the output will be sorted.
        """

        results = []
        bracket_level = 0
        part = ""

        for c in hostlist + ",":
            if c == "," and bracket_level == 0:
                # Comma at top level, split!
                if part:
                    results.extend(self.expand_part(part))
                part = ""
            else:
                part += c

            if c == "[":
                bracket_level += 1
            elif c == "]":
                bracket_level -= 1

            if bracket_level > 1:
                raise BadHostlist("nested brackets")
            elif bracket_level < 0:
                raise BadHostlist("unbalanced brackets")

        if bracket_level > 0:
            raise BadHostlist("unbalanced brackets")

        if not allow_duplicates:
            results = self.remove_duplicates(results)
        if sort:
            results = self.numerically_sorted(results)
        return results

    def expand_part(self, s):
        """Expand a part (e.g. "x[1-2]y[1-3][1-3]") (no outer level commas)."""

        # Base case: the empty part expand to the singleton list of ""
        if s == "":
            return [""]

        # Split into:
        # 1) prefix string (may be empty)
        # 2) rangelist in brackets (may be missing)
        # 3) the rest

        m = re.match(r'([^,\[]*)(\[[^\]]*\])?(.*)', s)
        (prefix, rangelist, rest) = m.group(1, 2, 3)

        # Expand the rest first (here is where we recurse!)
        rest_expanded = self.expand_part(rest)

        # Expand our own part
        if not rangelist:
            # If there is no rangelist, our own contribution is the prefix only
            us_expanded = [prefix]
        else:
            # Otherwise expand the rangelist (adding the prefix before)
            us_expanded = self.expand_rangelist(prefix, rangelist[1:-1])

        # Combine our list with the list from the expansion of the rest
        # (but guard against too large results first)
        if len(us_expanded) * len(rest_expanded) > self.MAX_SIZE:
            raise BadHostlist("results too large")

        return [us_part + rest_part
                for us_part in us_expanded
                for rest_part in rest_expanded]

    def expand_rangelist(self, prefix, rangelist):
        """ Expand a rangelist (e.g. "1-10,14"), putting a prefix before."""
        # Split at commas and expand each range separately
        results = []
        for range_ in rangelist.split(","):
            results.extend(self.expand_range(prefix, range_))
        return results

    def expand_range(self, prefix, range_):
        """ Expand a range (e.g. 1-10 or 14), putting a prefix before."""

        # Check for a single number first
        m = re.match(r'^[0-9]+$', range_)
        if m:
            return ["%s%s" % (prefix, range_)]

        # Otherwise split low-high
        m = re.match(r'^([0-9]+)-([0-9]+)$', range_)
        if not m:
            raise BadHostlist("bad range")

        (s_low, s_high) = m.group(1, 2)
        low = int(s_low)
        high = int(s_high)
        width = len(s_low)

        if high < low:
            raise BadHostlist("start > stop")
        elif high - low > self.MAX_SIZE:
            raise BadHostlist("range too large")

        results = []
        for i in range(low, high+1):
            results.append("%s%0*d" % (prefix, width, i))
        return results

    def remove_duplicates(self, l):  # noqa
        """Remove duplicates from a list (but keep the order)."""
        seen = set()
        results = []
        for e in l:
            if e not in seen:
                results.append(e)
                seen.add(e)
        return results

    def numerically_sorted(self, l):  # noqa
        """Sort a list of hosts numerically.

        E.g. sorted order should be n1, n2, n10; not n1, n10, n2.
        """
        return sorted(l, key=self.numeric_sort_key)

    numeric_sort_key_regexp = re.compile("([0-9]+)|([^0-9]+)")

    def numeric_sort_key(self, x):
        """Compose a sorting key to compare strings "numerically":

        We split numerical (integer) and non-numerical parts into a list,
        making sure that the numerical parts are converted to Python ints,
        and then sort on the lists. Thus, if we sort x10y and x9z8, we will
        compare ["x", 10, "y"] with ["x", 9, "x", "8"] and return x9z8
        before x10y".

        Python 3 complication: We cannot compare int and str, so while we can
        compare x10y and x9z8, we cannot compare x10y and 9z8. Kludge: insert
        a blank string first if the list would otherwise start with an integer.
        This will give the same ordering as before, as integers seem to compare
        smaller than strings in Python 2.
        """

        keylist = [int(i_ni[0]) if i_ni[0] else i_ni[1]
                   for i_ni in self.numeric_sort_key_regexp.findall(x)]
        if keylist and isinstance(keylist[0], int):
            keylist.insert(0, "")
        return keylist

    def collect_hostlist(self, hosts, silently_discard_bad=False):
        """Collect a hostlist string from a Python list of hosts.

        We start grouping from the rightmost numerical part.
        Duplicates are removed.

        A bad hostname raises an exception (unless silently_discard_bad
        is true causing the bad hostname to be silently discarded instead).
        """

        # Split hostlist into a list of (host, "") for the iterative part.
        # (Also check for bad node names now)
        # The idea is to move already collected numerical parts from the
        # left side (seen by each loop) to the right side (just copied).

        left_right = []
        for host in hosts:
            # We remove leading and trailing whitespace first, and skip empty lines # noqa
            host = host.strip()
            if host == "":
                continue

            # We cannot accept a host containing any of the three special
            # characters in the hostlist syntax (comma and flat brackets)
            if re.search(r'[][,]', host):
                if silently_discard_bad:
                    continue
                else:
                    raise BadHostlist("forbidden character")

            left_right.append((host, ""))

        # Call the iterative function until it says it's done
        looping = True
        while looping:
            left_right, looping = self.collect_hostlist_1(left_right)
        return ",".join([left + right for left, right in left_right])

    def collect_hostlist_1(self, left_right):
        """Collect a hostlist string from a list of hosts (left+right).

        The input is a list of tuples (left, right). The left part
        is analyzed, while the right part is just passed along
        (it can contain already collected range expressions).
        """

        # Scan the list of hosts (left+right) and build two things:
        # *) a set of all hosts seen (used later)
        # *) a list where each host entry is preprocessed for correct sorting

        sortlist = []
        remaining = set()
        for left, right in left_right:
            host = left + right
            remaining.add(host)

            # Match the left part into parts
            m = re.match(r'^(.*?)([0-9]+)?([^0-9]*)$', left)
            (prefix, num_str, suffix) = m.group(1, 2, 3)

            # Add the right part unprocessed to the suffix.
            # This ensures than an already computed range expression
            # in the right part is not analyzed again.
            suffix = suffix + right

            if num_str is None:
                # A left part with no numeric part at all gets special treatment! # noqa
                # The regexp matches with the whole string as the suffix,
                # with nothing in the prefix or numeric parts.
                # We do not want that, so we move it to the prefix and put
                # None as a special marker where the suffix should be.
                assert prefix == ""
                sortlist.append(((host, None), None, None, host))
            else:
                # A left part with at least an numeric part
                # (we care about the rightmost numeric part)
                num_int = int(num_str)
                num_width = len(num_str)  # This width includes leading zeroes
                sortlist.append(((prefix, suffix), num_int, num_width, host))

        # Sort lexicographically, first on prefix, then on suffix, then on
        # num_int (numerically), then...
        # This determines the order of the final result.

        sortlist.sort()

        # We are ready to collect the result parts as a list of new (left,
        # right) tuples.

        results = []
        needs_another_loop = False

        # Now group entries with the same prefix+suffix combination (the
        # key is the first element in the sortlist) to loop over them and
        # then to loop over the list of hosts sharing the same
        # prefix+suffix combination.

        for ((prefix, suffix), group) in itertools.groupby(
            sortlist, key=lambda x: x[0]
        ):
            if suffix is None:
                # Special case: a host with no numeric part
                results.append(("", prefix))  # Move everything to the right part # noqa
                remaining.remove(prefix)
            else:
                # The general case. We prepare to collect a list of
                # ranges expressed as (low, high, width) for later
                # formatting.
                range_list = []

                for ((prefix2, suffix2), num_int, num_width, host) in group:
                    if host not in remaining:
                        # Below, we will loop internally to enumate a whole
                        # range at a time. We then remove the covered hosts
                        # from the set. Therefore, skip the host here if it
                        # is gone from the set.
                        continue
                    assert num_int is not None

                    # Scan for a range starting at the current host
                    low = num_int
                    while True:
                        host = "%s%0*d%s" % (prefix, num_width, num_int, suffix)  # noqa
                        if host in remaining:
                            remaining.remove(host)
                            num_int += 1
                        else:
                            break
                    high = num_int - 1
                    assert high >= low
                    range_list.append((low, high, num_width))

                # We have a list of ranges to format. We make sure
                # we move our handled numerical part to the right to
                # stop it from being processed again.
                needs_another_loop = True
                if len(range_list) == 1 and range_list[0][0] == range_list[0][1]: # noqa
                    # Special case to make sure that n1 is not shown as n[1] etc  # noqa
                    results.append((
                        prefix, "%0*d%s" % (
                            range_list[0][2],
                            range_list[0][0],
                            suffix)))
                else:
                    # General case where high > low
                    f_range_list = [self.format_range(l, h, w) for l, h, w in range_list]  # noqa
                    results.append((
                        prefix, "[" + ",".join(f_range_list) + "]" + suffix
                    ))

        # At this point, the set of remaining hosts should be empty and we
        # are ready to return the result, together with the flag that says
        # if we need to loop again (we do if we have added something to a
        # left part).
        assert not remaining
        return results, needs_another_loop

    def format_range(self, low, high, width):
        """Format a range from low to high inclusively
        with a certain width."""

        if low == high:
            return "%0*d" % (width, low)
        return "%0*d-%0*d" % (width, low, width, high)


class HostlistFoldView(HostlistMixin, APIView):
    def post(self, request):
        hosts = request.data.get("hosts", "").split(",")
        return Response(self.collect_hostlist(hosts))


class HostlistExpandView(HostlistMixin, APIView):
    def post(self, request):
        hosts = request.data.get("hosts", "")
        return Response(self.expand_hostlist(hosts))
