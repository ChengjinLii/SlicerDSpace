"""Atlas-scoped region lookup shared by the GUI, requests and cohort jobs."""

import re
import unicodedata


# These translate names, never atlas label numbers. Matches still come from the LUT.
ALIASES = {
    "海马": "hippocampus", "杏仁核": "amygdala", "丘脑": "thalamus",
    "尾状核": "caudate", "壳核": "putamen", "苍白球": "pallidum",
    "伏隔核": "accumbens", "中央前回": "precentral", "中央后回": "postcentral",
    "楔前叶": "precuneus", "岛叶": "insula", "梭状回": "fusiform",
    "海马旁回": "parahippocampal", "外侧枕叶": "lateraloccipital",
    "胼胝体": "corpuscallosum", "脑干": "brainstem",
}


def region_identity(name):
    """Return hemisphere, exact structural name and compartment when encoded."""
    name = unicodedata.normalize("NFKC", str(name)).casefold().strip()
    match = re.match(r"^(?:(ctx|wm)[-_ ])?(left|right|lh|rh)[-_ ]+(.+)$", name)
    if not match:
        return None, re.sub(r"[^a-z0-9]+", "", name), None
    compartment, side, base = match.groups()
    return ("left" if side in {"left", "lh"} else "right"), re.sub(r"[^a-z0-9]+", "", base), compartment


def _tokens(query):
    query = unicodedata.normalize("NFKC", str(query)).casefold().strip()
    for alias in sorted(ALIASES, key=len, reverse=True):
        query = query.replace(alias, " " + ALIASES[alias] + " ")
    for alias, replacement in (("左侧", "left "), ("右侧", "right "), ("左", "left "), ("右", "right ")):
        query = query.replace(alias, replacement)
    tokens = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
    return [{"lh": "left", "rh": "right"}.get(token, token) for token in tokens]


def matches_region(region, query):
    query = str(query or "").strip()
    if not query:
        return True
    if re.fullmatch(r"[\d\s,;，；]+", query):
        return int(region["id"]) in {int(value) for value in re.findall(r"\d+", query)}
    side, base, compartment = region_identity(region["name"])
    searchable = " ".join((side or "", base, compartment or "", str(region["name"]).casefold()))
    tokens = _tokens(query)
    return bool(tokens) and all(token in searchable for token in tokens)


def resolve_regions(regions, selectors, *, allow_empty=False):
    """Resolve exact IDs/names or unambiguous aliases; never guess ambiguous labels."""
    if selectors is None:
        selectors = []
    if isinstance(selectors, str):
        selectors = [value.strip() for value in re.split(r"[,;，；\n]+", selectors) if value.strip()]
    if not isinstance(selectors, (list, tuple)):
        raise ValueError("Region selectors must be a list of names/IDs or comma-separated text")
    lookup = {row["id"]: row for row in regions}
    result = set()
    for value in selectors:
        if type(value) is int or isinstance(value, str) and value.strip().isdigit():
            label = int(value)
            if label not in lookup:
                raise ValueError("Region ID is absent from this atlas: " + str(label))
            result.add(label)
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Region names must be nonempty strings or positive integer IDs")
        exact = [row for row in regions if row["name"].casefold() == value.strip().casefold()]
        candidates = exact or [row for row in regions if matches_region(row, value)]
        if len(candidates) != 1:
            details = ", ".join(f'{row["id"]}: {row["name"]}' for row in candidates[:12])
            raise ValueError(("Ambiguous region" if candidates else "Unknown region") + f" {value!r}" +
                             ("; choose an ID: " + details if candidates else " in this atlas"))
        result.add(candidates[0]["id"])
    if not result and not allow_empty:
        raise ValueError("Select at least one region name or positive integer ID")
    return sorted(result)
