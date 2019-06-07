import logging

LOG = logging.getLogger(__name__)


class ScratchPad(dict):
    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        if item not in self:
            self[item] = ScratchPad()
        return self[item]

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, item):
        del self[item]
