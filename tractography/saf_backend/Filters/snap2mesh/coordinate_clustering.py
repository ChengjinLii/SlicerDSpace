import time

from sklearn.cluster import KMeans

try:
    from threadpoolctl import threadpool_limits
except Exception:  # pragma: no cover - optional sklearn dependency helper
    threadpool_limits = None


def coordinate_clustering(p, nsl):
    if nsl > 5e5:
        k = int(round(p.shape[0] ** 0.5))
    else:
        k = 60
    t0 = time.time()
    km = KMeans(n_clusters=k, n_init=10, random_state=0)
    if threadpool_limits is None:
        labels = km.fit_predict(p)
    else:
        with threadpool_limits(limits=1):
            labels = km.fit_predict(p)
    labels = labels + 1
    elapsed = [f"Time spent on surface coordinate clustering (k={k}):", _format_elapsed(time.time() - t0)]
    return labels, elapsed


def _format_elapsed(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
