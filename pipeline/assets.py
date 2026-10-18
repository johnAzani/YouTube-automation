"""B-roll acquisition, free-tier only.

Chain (first hit wins per clip slot):
  1. Pexels videos/photos  — free API key, commercial use, no attribution
  2. Pixabay videos/photos — free API key, commercial use
  3. Wikimedia Commons     — keyless, CC/PD (attribution recorded in credits)
  4. NASA Image Library    — keyless, public domain
  5. Generated title card  — offline ffmpeg fallback so the build never fails

Every asset's provenance is logged to credits.json so licences stay auditable.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from .config import CONFIG

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None


@dataclass
class Asset:
    path: Path
    source: str          # pexels | pixabay | wikimedia | nasa | generated
    origin_url: str
    license_note: str
    kind: str            # video | image
    query: str = ""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "asset"


def _cache_path(source: str, ident: str, ext: str) -> Path:
    key = hashlib.sha1(f"{source}:{ident}".encode()).hexdigest()[:16]
    path = CONFIG.ASSET_CACHE_DIR / f"{source}_{key}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _http_get(url: str, **kwargs) -> "requests.Response | None":
    if requests is None:
        return None
    try:
        resp = requests.get(url, timeout=25, **kwargs)
        resp.raise_for_status()
        return resp
    except Exception as exc:  # noqa: BLE001 - degradation is the point
        print(f"[assets] GET {url} failed: {exc!r}")
        return None


def _download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    if requests is None:
        return False
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        return dest.stat().st_size > 0
    except Exception as exc:  # noqa: BLE001
        print(f"[assets] download failed {url}: {exc!r}")
        return False


# --------------------------------------------------------------------------
# Source adapters
# --------------------------------------------------------------------------

def _pexels(query: str, want_video: bool) -> Asset | None:
    if not CONFIG.pexels_api_key:
        return None
    headers = {"Authorization": CONFIG.pexels_api_key}
    if want_video:
        r = _http_get("https://api.pexels.com/videos/search",
                      params={"query": query, "per_page": 5, "orientation": "landscape"}, headers=headers)
        if r:
            for v in r.json().get("videos", []):
                files = sorted(v.get("video_files", []),
                               key=lambda f: abs((f.get("width") or 0) - CONFIG.width))
                if not files:
                    continue
                url = files[0]["link"]
                dest = _cache_path("pexels", str(v["id"]), "mp4")
                if _download(url, dest):
                    return Asset(dest, "pexels", v.get("url", ""), "Pexels License (free commercial use)", "video", query)
    else:
        r = _http_get("https://api.pexels.com/v1/search",
                      params={"query": query, "per_page": 5, "orientation": "landscape"}, headers=headers)
        if r:
            for p in r.json().get("photos", []):
                url = p["src"].get("large2x") or p["src"].get("large") or p["src"].get("original")
                dest = _cache_path("pexels", str(p["id"]), "jpg")
                if url and _download(url, dest):
                    return Asset(dest, "pexels", p.get("url", ""), "Pexels License (free commercial use)", "image", query)
    return None


def _pixabay(query: str, want_video: bool) -> Asset | None:
    if not CONFIG.pixabay_api_key:
        return None
    base = "https://pixabay.com/api/videos/" if want_video else "https://pixabay.com/api/"
    params = {"key": CONFIG.pixabay_api_key, "q": query, "per_page": 5, "safesearch": "true"}
    if not want_video:
        params.update({"image_type": "photo", "orientation": "horizontal"})
    r = _http_get(base, params=params)
    if not r:
        return None
    hits = r.json().get("hits", [])
    for h in hits:
        if want_video:
            versions = h.get("videos", {})
            url = (versions.get("medium") or versions.get("small") or {}).get("url")
            ext = "mp4"
        else:
            url = h.get("largeImageURL") or h.get("webformatURL")
            ext = "jpg"
        if not url:
            continue
        dest = _cache_path("pixabay", str(h["id"]), ext)
        if _download(url, dest):
            kind = "video" if want_video else "image"
            return Asset(dest, "pixabay", h.get("pageURL", ""), "Pixabay Content License (free commercial use)", kind, query)
    return None


def _wikimedia(query: str) -> Asset | None:
    r = _http_get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 5,
            "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1920,
        },
        headers={"User-Agent": "YouTubeAutomationPipeline/1.0 (educational project)"},
    )
    if not r:
        return None
    pages = (r.json().get("query") or {}).get("pages") or {}
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        url = info.get("thumburl") or info.get("url")
        dest = _cache_path("wikimedia", page.get("title", url or ""), "jpg")
        if url and _download(url, dest):
            lic = (info.get("extmetadata") or {}).get("LicenseShortName", {}).get("value", "see Commons")
            return Asset(dest, "wikimedia", info.get("descriptionurl", ""), f"Wikimedia Commons — {lic} (attribution required)", "image", query)
    return None


def _nasa(query: str) -> Asset | None:
    r = _http_get("https://images-api.nasa.gov/search", params={"q": query, "media_type": "image"})
    if not r:
        return None
    items = (r.json().get("collection") or {}).get("items") or []
    for item in items[:5]:
        data = (item.get("data") or [{}])[0]
        links = item.get("links") or []
        url = next((l.get("href") for l in links if l.get("render") == "image"), None)
        if not url:
            continue
        dest = _cache_path("nasa", data.get("nasa_id", url), "jpg")
        if _download(url, dest):
            return Asset(dest, "nasa", item.get("href", ""), "NASA media — public domain", "image", query)
    return None


def _title_card(query: str, scene_no: int, out_dir: Path, title: str = "") -> Asset:
    """Offline fallback: a branded solid card with the scene text. Always works."""
    from .textplates import render_text_plate

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"card_{scene_no:02d}_{_slugify(query)[:24]}.png"

    palette = [(22, 33, 62), (15, 52, 96), (83, 52, 131), (27, 67, 50), (61, 43, 31)]
    color = palette[scene_no % len(palette)]
    try:
        render_text_plate(
            dest, title=(title or query), subtitle=f"Scene {scene_no // 10}",
            bg_color=color, title_size=42,
        )
    except Exception:
        from PIL import Image

        Image.new("RGB", (CONFIG.width, CONFIG.height), color).save(dest)
    return Asset(dest, "generated", "n/a (generated placeholder)", "generated", "image", query)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def fetch_scene_assets(query: str, scene_no: int, out_dir: Path, count: int | None = None) -> list[Asset]:
    count = count or CONFIG.clips_per_scene
    assets: list[Asset] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    q = query.strip() or "cinematic landscape"

    sources = [
        ("pexels", lambda: _pexels(q, want_video=True)),
        ("pexels", lambda: _pexels(q, want_video=False)),
        ("pixabay", lambda: _pixabay(q, want_video=True)),
        ("pixabay", lambda: _pixabay(q, want_video=False)),
    ]
    if CONFIG.enable_keyless_sources:
        sources += [
            ("wikimedia", lambda: _wikimedia(q)),
            ("nasa", lambda: _nasa(q)),
        ]

    for i in range(count):
        got: Asset | None = None
        for name, fn in sources:
            try:
                got = fn()
            except Exception as exc:  # noqa: BLE001
                print(f"[assets] source {name} errored: {exc!r}")
                got = None
            if got is not None:
                got.query = q
                assets.append(got)
                break
        if got is None:
            assets.append(_title_card(q, scene_no * 10 + i, out_dir, title=q))

    _write_credits(out_dir, assets)
    return assets


def _write_credits(out_dir: Path, assets: list[Asset]) -> None:
    credits_path = out_dir / "credits.json"
    existing: list[dict] = []
    if credits_path.exists():
        try:
            existing = json.loads(credits_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            existing = []
    for a in assets:
        d = asdict(a)
        d["path"] = str(a.path)
        existing.append(d)
    credits_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
