cat > graph.py <<'EOF'
import heapq


def shortest_path(graph, source, target):
    dist = {source: 0}
    prev = {}
    heap = [(0, 0, source)]
    counter = 1
    done = set()
    while heap:
        d, _, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == target:
            break
        for v, w in graph.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, counter, v))
                counter += 1
    if target not in done:
        return None, []
    def build(node):
        return [node] if node == source else build(prev[node]) + [node]
    return dist[target], build(target)
EOF
