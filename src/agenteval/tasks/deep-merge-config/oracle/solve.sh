cat > config_merge.py <<'EOF'
import copy


def merge(base, override):
    """Deep-merge two configuration dictionaries and return a new dictionary."""
    result = {k: copy.deepcopy(v) for k, v in base.items()}
    for key, value in override.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        elif isinstance(value, dict):
            result[key] = merge({}, value)
        else:
            result[key] = copy.deepcopy(value)
    return result
EOF
