import asyncio


class Dispatcher:
    def __init__(self, worker_cap=3):
        self.worker_cap = worker_cap

    def compute_ready_set(self, slices):
        done_ids = {s["id"] for s in slices if s.get("status") == "done"}
        ready = [
            s for s in slices
            if s.get("status") == "pending"
            and all(b in done_ids for b in s.get("blocked_by", []))
        ]
        return ready[:self.worker_cap]

    def validate_slices(self, slices):
        ids = {s["id"] for s in slices}
        for s in slices:
            if s["id"] in s.get("blocked_by", []):
                raise ValueError(f"Slice {s['id']} references itself in blocked_by")
        graph = {s["id"]: [b for b in s.get("blocked_by", []) if b in ids] for s in slices}
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    raise ValueError("Circular dependency detected in slices")
            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node)

    async def dispatch(self, slices, workspace_dir):
        self.validate_slices(slices)
        ready = self.compute_ready_set(slices)
        if ready:
            for s in ready:
                s["status"] = "in_progress"
            await asyncio.gather(*[
                self._spawn_worker(s, workspace_dir) for s in ready
            ])

    async def _spawn_worker(self, slice, workspace_dir):
        raise NotImplementedError("Worker spawning not implemented")
