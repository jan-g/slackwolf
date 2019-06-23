import logging
import os
import os.path
import pickle
import tempfile

LOG = logging.getLogger(__name__)

DATA_DIR = None


def _data_dir():
    global DATA_DIR
    DATA_DIR = DATA_DIR or os.environ.get('DATA_DIR') or tempfile.mkdtemp()
    return DATA_DIR


def save(key, obj):
    dir = _data_dir()
    key = str(key)
    file = os.path.join(dir, key)
    temp = os.path.join(dir, key + "~")
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
    dir = _data_dir()
    key = str(key)
    file = os.path.join(dir, key)
    try:
        with open(file, 'rb') as f:
            store = pickle.load(f)
        return factory(store)
    except IOError:
        return default()


def drop(key):
    dir = _data_dir()
    key = str(key)
    file = os.path.join(dir, key)
    try:
        os.unlink(file)
    except IOError:
        LOG.exception("Problem unlinking persisted file {}".format(file))
