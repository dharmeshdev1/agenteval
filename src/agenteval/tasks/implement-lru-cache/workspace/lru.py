class LRUCache:
    """Least-recently-used cache with a fixed capacity."""

    def __init__(self, capacity):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

    def put(self, key, value):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def keys(self):
        raise NotImplementedError
