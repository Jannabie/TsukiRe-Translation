"""
scene_map_loader.py — Load scene_map.json and build the offset-to-scene index.

scene_map.json format:
  {
    "Route|Day|filename.txt": [[start_offset, end_offset], ...],
    ...
  }

Returns:
  o2s          : {offset → (route, day, filename)}
  scene_tree   : {route → {day → [filename, ...]}}  (ordered)
  scene_offsets: {(route, day, filename) → [offset, ...]}
"""

import json, os, re


_ROUTE_ORDER = ["Common", "Arcueid", "Ciel", "QA"]


def load_scene_map(
    json_path: str | None = None,
) -> tuple[dict, dict, dict]:
    """Load scene_map.json and return (o2s, scene_tree, scene_offsets).

    If *json_path* is None the function looks for scene_map.json in the same
    directory as this module file.

    All three dicts are empty if the JSON cannot be found or parsed.
    """
    if json_path is None:
        json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "scene_map.json"
        )

    if not os.path.exists(json_path):
        return {}, {}, {}

    try:
        raw: dict = json.load(open(json_path, encoding="utf-8"))
    except Exception:
        return {}, {}, {}

    o2s: dict         = {}
    scene_offsets: dict = {}

    for key, ranges in raw.items():
        parts = key.split("|")
        if len(parts) < 3:
            continue
        route, day, fname = parts[0], parts[1], parts[2]
        sk = (route, day, fname)
        scene_offsets[sk] = []
        for s, e in ranges:
            for o in range(s, e + 1):
                o2s[o] = sk
                scene_offsets[sk].append(o)

    def _day_key(d: str) -> int:
        m = re.search(r"(\d+)", d)
        return int(m.group(1)) if m else -1

    tree: dict = {}
    for sk in scene_offsets:
        r, d, f = sk
        tree.setdefault(r, {}).setdefault(d, []).append(f)

    for r in tree:
        for d in tree[r]:
            tree[r][d].sort()
        tree[r] = dict(sorted(tree[r].items(), key=lambda x: _day_key(x[0])))

    ordered_tree = {r: tree[r] for r in _ROUTE_ORDER if r in tree}
    # Append any routes not in the standard order
    for r in tree:
        if r not in ordered_tree:
            ordered_tree[r] = tree[r]

    return o2s, ordered_tree, scene_offsets