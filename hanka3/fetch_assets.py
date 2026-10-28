# Download the CC0 Poly Haven source assets (about 1 GB) the build and impostor bake read:
#   python3 hanka3/fetch_assets.py hanka3/assets_src fern_02 moss_01 dry_branches_medium_01 grass_medium_01 \
#     dead_tree_trunk fir_sapling pine_sapling_small fir_tree_01 pine_tree_01
import json, os, sys, urllib.request
opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "dom-3d-asset-fetch/1.0 (CC0 Poly Haven assets)")]
urllib.request.install_opener(opener)
out = sys.argv[1]
names = sys.argv[2:]
for n in names:
    files = json.load(urllib.request.urlopen(f"https://api.polyhaven.com/files/{n}"))
    node = files["blend"]["1k"]["blend"]
    base = os.path.join(out, n)
    os.makedirs(base, exist_ok=True)
    jobs = [(node["url"], os.path.join(base, os.path.basename(node["url"])))]
    for rel, inc in node.get("include", {}).items():
        jobs.append((inc["url"], os.path.join(base, rel)))
    for url, dst in jobs:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            urllib.request.urlretrieve(url, dst)
    print("done", n, flush=True)
