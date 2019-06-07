import logging
import os
import os.path
import pickle

LOG = logging.getLogger(__name__)

DATA_DIR = None


def save(key, obj):
    global DATA_DIR
    DATA_DIR = DATA_DIR or os.environ['DATA_DIR']
    key = str(key)
    file = os.path.join(DATA_DIR, key)
    temp = os.path.join(DATA_DIR, key + "~")
    store = obj.save()

    try:
        with open(temp, 'wb') as f:
            pickle.dump(store, f)
        os.rename(temp, file)
    except Exception:
        LOG.exception("Problem saving {}".format(key))
        try:
            os.unlink(temp)
        except IOError:
            LOG.exception("Problem unlinking temporary file {}".format(temp))


def load(key, default=None, factory=None):
    global DATA_DIR
    DATA_DIR = DATA_DIR or os.environ['DATA_DIR']
    key = str(key)
    file = os.path.join(DATA_DIR, key)
    try:
        with open(file, 'rb') as f:
            store = pickle.load(f)
        return factory(store)
    except IOError:
        return default()


def drop(key):
    global DATA_DIR
    DATA_DIR = DATA_DIR or os.environ['DATA_DIR']
    key = str(key)
    file = os.path.join(DATA_DIR, key)
    try:
        os.unlink(file)
    except IOError:
        LOG.exception("Problem unlinking persisted file {}".format(file))
