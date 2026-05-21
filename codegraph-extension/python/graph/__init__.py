"""graph - extract · build · cluster · analyze · report."""
import sys
from pathlib import Path
dep_dir = Path(__file__).parent.parent / "dependencies"
if dep_dir.exists() and str(dep_dir) not in sys.path:
    sys.path.insert(0, str(dep_dir))



def __getattr__(name):
    # Lazy imports so `graph install` works before heavy deps are in place.
    _map = {
        "extract": ("graph.extract", "extract"),
        "collect_files": ("graph.extract", "collect_files"),
        "build_from_json": ("graph.build", "build_from_json"),
        "cluster": ("graph.cluster", "cluster"),
        "score_all": ("graph.cluster", "score_all"),
        "cohesion_score": ("graph.cluster", "cohesion_score"),
        "god_nodes": ("graph.analyze", "god_nodes"),
        "surprising_connections": ("graph.analyze", "surprising_connections"),
        "suggest_questions": ("graph.analyze", "suggest_questions"),
        "generate": ("graph.report", "generate"),
        "to_json": ("graph.export", "to_json"),
        "to_html": ("graph.export", "to_html"),
        "to_svg": ("graph.export", "to_svg"),
        "to_canvas": ("graph.export", "to_canvas"),
        "to_wiki": ("graph.wiki", "to_wiki"),
    }
    if name in _map:
        import importlib
        mod_name, attr = _map[name]
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr)
    raise AttributeError(f"module 'graph' has no attribute {name!r}")
