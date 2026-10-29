import copy
import random
import time
import unittest

from graph import shortest_path


def bellman_ford(graph, source):
    nodes = set(graph) | {v for edges in graph.values() for v, _ in edges}
    dist = {n: float("inf") for n in nodes}
    dist[source] = 0
    for _ in range(len(nodes)):
        changed = False
        for u, edges in graph.items():
            for v, w in edges:
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    changed = True
        if not changed:
            break
    return dist


def check_path(graph, path, source, target, distance):
    assert path[0] == source and path[-1] == target, path
    total = 0
    for a, b in zip(path, path[1:]):
        weights = [w for v, w in graph.get(a, []) if v == b]
        assert weights, "path uses an edge that does not exist: %r -> %r" % (a, b)
        total += min(weights)
    assert total == distance, "path length %r does not match distance %r" % (total, distance)


def grid(n):
    g = {}
    for r in range(n):
        for c in range(n):
            edges = []
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < n and 0 <= cc < n:
                    edges.append(((rr, cc), 1 + (rr * 7 + cc * 13) % 5))
            g[(r, c)] = edges
    return g


class Hidden(unittest.TestCase):
    def test_matches_bellman_ford_on_random_graphs(self):
        rng = random.Random(7)
        for trial in range(60):
            n = rng.randint(2, 25)
            g = {i: [] for i in range(n)}
            for _ in range(rng.randint(0, 4 * n)):
                g[rng.randrange(n)].append((rng.randrange(n), rng.randint(0, 9)))
            source, target = rng.randrange(n), rng.randrange(n)
            want = bellman_ford(g, source)[target]
            dist, path = shortest_path(g, source, target)
            if want == float("inf"):
                self.assertEqual((dist, path), (None, []))
            else:
                self.assertEqual(dist, want)
                check_path(g, path, source, target, dist)

    def test_source_equals_target(self):
        self.assertEqual(shortest_path({"a": [("b", 1)]}, "a", "a"), (0, ["a"]))
        self.assertEqual(shortest_path({}, "a", "a"), (0, ["a"]))

    def test_zero_weight_edges_and_missing_keys(self):
        g = {"a": [("b", 0)], "b": [("c", 0)]}
        self.assertEqual(shortest_path(g, "a", "c"), (0, ["a", "b", "c"]))

    def test_nodes_without_an_entry_are_handled_before_the_target(self):
        # "ghost" is reached at cost 0 and is only ever a neighbour, never a key
        g = {"a": [("ghost", 0), ("b", 1)], "b": [("c", 1)]}
        self.assertEqual(shortest_path(g, "a", "c"), (2, ["a", "b", "c"]))

    def test_graph_is_not_modified(self):
        g = grid(8)
        before = copy.deepcopy(g)
        shortest_path(g, (0, 0), (7, 7))
        self.assertEqual(g, before)

    def test_large_grid_is_fast(self):
        g = grid(200)
        start = time.perf_counter()
        dist, path = shortest_path(g, (0, 0), (199, 199))
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 2.0, "took %.1fs on a 200x200 grid" % elapsed)
        check_path(g, path, (0, 0), (199, 199), dist)

    def test_long_chain_without_recursion(self):
        n = 40000
        g = {i: [(i + 1, 1)] for i in range(n)}
        start = time.perf_counter()
        dist, path = shortest_path(g, 0, n)
        self.assertLess(time.perf_counter() - start, 2.0)
        self.assertEqual(dist, n)
        self.assertEqual(len(path), n + 1)

    def test_dense_random_graph_is_fast_and_correct(self):
        rng = random.Random(3)
        n = 4000
        g = {i: [] for i in range(n)}
        for _ in range(40000):
            g[rng.randrange(n)].append((rng.randrange(n), rng.randint(0, 20)))
        start = time.perf_counter()
        dist, path = shortest_path(g, 0, n - 1)
        self.assertLess(time.perf_counter() - start, 2.0)
        want = bellman_ford(g, 0)[n - 1]
        if want == float("inf"):
            self.assertEqual((dist, path), (None, []))
        else:
            self.assertEqual(dist, want)
            check_path(g, path, 0, n - 1, dist)


if __name__ == "__main__":
    unittest.main()
