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
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key, value):
        if key in self._data:
            self._data[key] = value
            return
        self._data[key] = value
        if len(self._data) > self._capacity:
            self._data.popitem(last=False)
EOF
