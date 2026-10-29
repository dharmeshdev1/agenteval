def shortest_path(graph, source, target):
    """Dijkstra's algorithm. Correct but slow: it scans every reached node on each step."""
    dist = {source: 0}
    prev = {}
    done = set()
    while True:
        candidates = [n for n in dist if n not in done]
        if not candidates:
            break
        u = min(candidates, key=lambda n: dist[n])
        done.add(u)
        if u == target:
            break
        for v, w in graph.get(u, []):
            nd = dist[u] + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
    if target not in done:
        return None, []
    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    path.reverse()
    return dist[target], path
