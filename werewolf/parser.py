import re
from .sentinel import Sentinel


def kleene(parser):
    def parse_many(text):
        text = text.lstrip()
        if len(text) > 0:
            for item, text1 in parser(text):
                for items, text2 in parse_many(text1):
                    yield ([item] + items, text2)
            else:
                yield([], text)
        else:
            yield ([], text)
    return parse_many


def max_kleene(parser):
    def parse_many(text):
        text = text.lstrip()
        any = False
        for item, text1 in parser(text):
            for items, text2 in parse_many(text1):
                any = True
                yield ([item] + items, text2)
        if not any:
            yield ([], text)
    return parse_many


def cat(*parsers):
    def parse_cat(text, parsers=parsers):
        for item1, text1 in parsers[0](text):
            first = (item1,) if item1 is not DROP else ()
            if len(parsers) == 1:
                yield first, text1
            else:
                for rest, text2 in parse_cat(text1, parsers=parsers[1:]):
                    yield first + rest, text2
    return parse_cat


def alt(*parsers):
    def parse_alt(text):
        for parser in parsers:
            for item, text1 in parser(text):
                yield item, text1
    return parse_alt


def maybe(parser):
    def parse_maybe(text):
        yield from parser(text)
        yield None, text
    return parse_maybe


def token(string):
    def parse_token(text):
        text = text.lstrip()
        if text.startswith(string):
            yield string, text[len(string):]
    return parse_token


DROP = Sentinel("DROP")


def map(parser, func):
    def parse_map(text):
        for item, text1 in parser(text):
            yield func(item), text1
    return parse_map


def drop_token(string):
    return map(token(string), lambda _: DROP)


EOS = Sentinel("EOS")


def eos(text):
    text = text.lstrip()
    if len(text) == 0:
        yield (EOS, text)


NATURAL = re.compile(r'^([0-9]+)')


def natural(text):
    text = text.lstrip()
    match = NATURAL.match(text)
    if match is not None:
        yield int(match.group(1)), text[match.end():]
