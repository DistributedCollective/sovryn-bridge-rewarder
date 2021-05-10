from dataclasses import is_dataclass, asdict
from textwrap import indent
from typing import List, Dict, Any, Union
from pprint import pprint, pformat
from web3.datastructures import AttributeDict


def pprint_improved(thing):
    pprint(convert_to_pprintable(thing))


def convert_to_pprintable(a: Any):
    if isinstance(a, list):
        return [convert_to_pprintable(x) for x in a]
    if is_dataclass(a):
        body = pformat(asdict(a))
        return ReprStr(f'{a.__class__.__name__}({body})')
    if isinstance(a, AttributeDict):
        return {
            k: convert_to_pprintable(v)
            for (k, v) in a.items()
        }
    return a


class ReprStr:
    def __init__(self, repr_str):
        self.repr_str = repr_str

    def __repr__(self):
        return self.repr_str
