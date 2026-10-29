cat > lru.py <<'EOF'
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity")
        self._capacity = capacity
        self._data = OrderedDict()

    def __len__(self):
        return len(self._data)

    def keys(self):
        return list(self._data)

    def get(self, key):
        return self._data.get(key)

    def put(self, key, value):
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self._capacity:
            self._data.popitem(last=False)
EOF
