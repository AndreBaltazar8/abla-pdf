#!/usr/bin/env python3
"""Takes a CMS SignedData apart: signature-bytes.py in.p7s attributes-out signature-out. The
attributes are written as they're signed, with their SET tag instead of the [0] in the CMS."""
import sys


def items(data, at, end):
    while at < end:
        tag = data[at]
        length = data[at + 1]
        head = 2
        if length & 0x80:
            head = 2 + (length & 0x7f)
            length = int.from_bytes(data[at + 2:at + head], "big")
        yield tag, at, at + head, at + head + length
        at += head + length


data = open(sys.argv[1], "rb").read()
_, _, begin, end = next(items(data, 0, len(data)))
wrapper = [i for i in items(data, begin, end) if i[0] == 0xa0][0]
_, _, begin, end = next(items(data, wrapper[2], wrapper[3]))
signer_infos = [i for i in items(data, begin, end) if i[0] == 0x31][-1]
_, _, begin, end = next(items(data, signer_infos[2], signer_infos[3]))
fields = list(items(data, begin, end))
attributes = [f for f in fields if f[0] == 0xa0][0]
signature = [f for f in fields if f[0] == 0x04][-1]
open(sys.argv[2], "wb").write(b"\x31" + data[attributes[1] + 1:attributes[3]])
open(sys.argv[3], "wb").write(data[signature[2]:signature[3]])
