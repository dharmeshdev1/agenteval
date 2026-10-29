cat > lru.py <<'EOF'
from collections import OrderedDict


class LRUCache:
    """Least-recently-used cache with a fixed capacity."""

    def __init__(self, capacity):
        if not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._data = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key, value):
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def __len__(self):
        return len(self._data)

    def keys(self):
        return list(self._data)
EOF
