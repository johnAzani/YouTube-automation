"""License-aware, clip-first B-roll acquisition. All providers have free access.

Tries video across enabled platforms before falling back to photography. The
renderer must contain-fit assets (never stretch or crop); provenance is logged.
Sources: Pexels/Pixabay (free API keys), Openverse, Wikimedia Commons,
Internet Archive, and NASA. Only usable/licensed matches are returned by default;
generic title cards require an explicit opt-in.
"""
from __future__ import annotations
import hashlib, json, mimetypes, re, time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse, quote
from .config import CONFIG, ASSET_CACHE_DIR
try:
    import requests  # type: ignore
except ImportError:
    requests = None

# Wikimedia asks for a descriptive User-Agent with contact info; a generic one
# lands in a harsher rate-limit bucket (we were seeing upload.wikimedia.org 429s).
_UA_API = "YouTubeAutomationPipeline/2.0 (https://github.com/johnAzani/YouTube-automation; educational b-roll search)"
_UA_DL = "YouTubeAutomation/2.0 (https://github.com/johnAzani/YouTube-automation; free stock media download)"

@dataclass
class Asset:
    path: Path
    source: str
    origin_url: str
    license_note: str
    kind: str
    query: str = ""
    width: int = 0
    height: int = 0

def _slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "asset"

# Per-provider attempt detail for the most recent call. Providers set this on
# every early exit ("no API key", "0 results", "10 results, 0 licensed-usable",
# "search request failed: …") so fetch_scene_assets can log *why* a source
# missed instead of only that it returned nothing. Cleared before each call.
_PROBE: dict[str, str] = {}


def _probe(name: str, detail: str) -> None:
    _PROBE[name] = detail

def _cache_path(source, ident, ext):
    key = hashlib.sha1(f"{source}:{ident}".encode()).hexdigest()[:16]
    path = ASSET_CACHE_DIR / f"{source}_{key}.{ext.lstrip('.')}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

# Last failure reasons, one line each, so attempt probes can quote them
# ("search request failed: HTTPError('404 …')" beats a bare "request failed"
# when the only readable output is a one-line CI annotation).
_HTTP_ERR = ""
_DL_ERR = ""

def _http_get(url, **kwargs):
    """GET with one retry on transient upstream trouble (429 / 5xx, honouring
    Retry-After). Timeouts and 4xx fail immediately — retrying those just
    burns the CI budget."""
    global _HTTP_ERR
    if requests is None:
        _HTTP_ERR = "requests module not installed"; return None
    kwargs.setdefault("timeout", (6, 16))
    for attempt in (1, 2):
        try:
            resp = requests.get(url, **kwargs)
            resp.raise_for_status()
            _HTTP_ERR = ""; return resp
        except Exception as exc:
            _HTTP_ERR = " ".join(repr(exc).split())[:300]
            resp_obj = getattr(exc, "response", None)
            status = getattr(resp_obj, "status_code", None)
            if attempt == 1 and status and (status == 429 or status >= 500):
                wait = min(float(resp_obj.headers.get("Retry-After") or 0) or 2.0, 8.0)
                print(f"[assets] GET {url} -> HTTP {status}, retrying in {wait:g}s", flush=True)
                time.sleep(wait)
                continue
            print(f"[assets] GET {url} failed: {exc!r}"); return None
    return None

def _dl_note(failures):
    return f", last error: {_DL_ERR}" if failures and _DL_ERR else ""

def _req_fail():
    return "search request failed" + (f": {_HTTP_ERR}" if _HTTP_ERR else "")

def _download(url, dest, max_bytes=120*1024*1024):
    """Stream an asset to disk. Retries transient failures (429/5xx with
    Retry-After, connection drops) up to twice; the 120 MB safety cap and
    timeouts are final — re-pulling a giant file would just burn the clock."""
    global _DL_ERR
    if dest.exists() and dest.stat().st_size > 1024: return True
    if requests is None or not url:
        _DL_ERR = "requests module not installed" if requests is None else "no url"; return False
    _DL_ERR = ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in (1, 2, 3):
        try:
            total=0
            with requests.get(url, stream=True, timeout=(8,30), headers={"User-Agent":_UA_DL}) as r:
                r.raise_for_status()
                with open(dest,"wb") as f:
                    for chunk in r.iter_content(1<<16):
                        if not chunk: continue
                        total += len(chunk)
                        if total > max_bytes: raise ValueError("asset exceeds 120 MB safety limit")
                        f.write(chunk)
            if dest.stat().st_size > 1024: return True
            _DL_ERR = "downloaded file under 1 KB"; return False
        except Exception as exc:
            _DL_ERR = " ".join(repr(exc).split())[:300]
            try: dest.unlink(missing_ok=True)
            except OSError: pass
            resp_obj = getattr(exc, "response", None)
            status = getattr(resp_obj, "status_code", None)
            retryable = (status and (status == 429 or status >= 500)) or isinstance(
                exc, (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError))
            if attempt < 3 and retryable:
                wait = min(float((resp_obj.headers.get("Retry-After") if resp_obj is not None else "") or 0) or 1.5 * attempt, 8.0)
                print(f"[assets] download {url} -> {'HTTP ' + str(status) if status else type(exc).__name__}, "
                      f"retrying in {wait:g}s", flush=True)
                time.sleep(wait)
                continue
            print(f"[assets] download failed {url}: {exc!r}"); return False
    return False

def _orientation(w,h):
    r=w/max(1,h)
    return "landscape" if r>1.15 else ("portrait" if r<0.87 else "square")

def _aspect_rank(item,w,h):
    iw,ih=int(item.get("width") or 0),int(item.get("height") or 0)
    if not iw or not ih: return (9.0,0)
    return (abs(iw/ih-w/max(1,h)), -min(iw*ih,w*h*4))

def _pexels(q,video,w,h):
    label=f"Pexels {'video' if video else 'photo'}"
    if not CONFIG.pexels_api_key:
        _probe(label,"no API key"); return None
    orient=_orientation(w,h); headers={"Authorization":CONFIG.pexels_api_key}
    if video:
        r=_http_get("https://api.pexels.com/videos/search",params={"query":q,"per_page":8,"orientation":orient},headers=headers)
        if not r: _probe(label,_req_fail()); return None
        vids=r.json().get("videos",[])
        if not vids: _probe(label,"0 results")
        for v in vids:
            files=sorted((f for f in v.get("video_files",[]) if f.get("link")),key=lambda f:_aspect_rank(f,w,h))
            for f in files[:2]:
                dest=_cache_path("pexels",str(v["id"]),"mp4")
                if _download(f["link"],dest):
                    _probe(label,"ok"); return Asset(dest,"pexels",v.get("url",""),"Pexels License — free, including commercial use","video",q,int(f.get("width") or 0),int(f.get("height") or 0))
        if vids: _probe(label,f"{len(vids)} results, none downloadable")
    else:
        r=_http_get("https://api.pexels.com/v1/search",params={"query":q,"per_page":8,"orientation":orient},headers=headers)
        if not r: _probe(label,_req_fail()); return None
        photos=r.json().get("photos",[])
        if not photos: _probe(label,"0 results")
        for p in photos:
            src=p.get("src") or {}; url=src.get("large2x") or src.get("large") or src.get("original")
            dest=_cache_path("pexels",str(p["id"]),"jpg")
            if url and _download(url,dest):
                _probe(label,"ok"); return Asset(dest,"pexels",p.get("url",""),"Pexels License — free, including commercial use","image",q,int(p.get("width") or 0),int(p.get("height") or 0))
        if photos: _probe(label,f"{len(photos)} results, none downloadable")
    return None

def _pixabay(q,video,w,h):
    label=f"Pixabay {'video' if video else 'photo'}"
    if not CONFIG.pixabay_api_key:
        _probe(label,"no API key"); return None
    orient="horizontal" if w>h else "vertical"; base="https://pixabay.com/api/videos/" if video else "https://pixabay.com/api/"
    params={"key":CONFIG.pixabay_api_key,"q":q,"per_page":8,"safesearch":"true","orientation":orient}
    if not video:params["image_type"]="photo"
    r=_http_get(base,params=params)
    if not r: _probe(label,_req_fail()); return None
    hits=r.json().get("hits",[])
    if not hits: _probe(label,"0 results")
    for hit in hits:
        if video:
            choices=sorted((hit.get("videos") or {}).values(),key=lambda f:_aspect_rank(f,w,h)); selected=next((x for x in choices if x.get("url")),{})
            url=selected.get("url"); ext="mp4"; sw,sh=selected.get("width",0),selected.get("height",0)
        else:url=hit.get("largeImageURL") or hit.get("webformatURL"); ext="jpg"; sw,sh=hit.get("imageWidth",0),hit.get("imageHeight",0)
        if not url:continue
        dest=_cache_path("pixabay",str(hit["id"]),ext)
        if _download(url,dest):
            _probe(label,"ok"); return Asset(dest,"pixabay",hit.get("pageURL",""),"Pixabay Content License — free; check depicted people/trademarks","video" if video else "image",q,int(sw or 0),int(sh or 0))
    if hits: _probe(label,f"{len(hits)} results, none downloadable")
    return None

def _openverse(q,video,w,h):
    label=f"Openverse {'video' if video else 'photo'}"
    endpoint='videos' if video else 'images'
    r=_http_get(f"https://api.openverse.org/v1/{endpoint}/",params={'q':q,'page_size':12,'license_type':'commercial'})
    if not r: _probe(label,_req_fail()); return None
    results=sorted(r.json().get('results',[]),key=lambda x:_aspect_rank(x,w,h))
    if not results: _probe(label,"0 results")
    bad_lic=bad_ext=bad_dl=0
    for item in results:
        url=item.get('url'); mime=item.get('mimetype') or ''; lic=str(item.get('license') or '').lower().replace('_','-')
        if not url or lic not in {'cc0','pdm','by','cc-zero','public-domain'}:
            bad_lic+=1; continue
        if video and item.get('duration') is not None and float(item.get('duration') or 0)<3:continue
        if video: ext='mp4' if ('mp4' in mime or url.lower().split('?')[0].endswith('.mp4')) else Path(urlparse(url).path).suffix.lstrip('.')
        else: ext=Path(urlparse(url).path).suffix.lstrip('.') or mimetypes.guess_extension(mime or 'image/jpeg').lstrip('.')
        if ext.lower() not in ({'mp4','webm','ogv','mov'} if video else {'jpg','jpeg','png','webp'}):
            bad_ext+=1; continue
        dest=_cache_path('openverse',item.get('id') or url,ext)
        if _download(url,dest):
            creator=item.get('creator') or 'creator not listed'
            note=f"Openverse — CC {item.get('license')} {item.get('license_version') or ''}; creator: {creator}; {item.get('attribution') or ''}; verify landing page"
            _probe(label,"ok")
            return Asset(dest,'openverse',item.get('foreign_landing_url') or url,note,'video' if video else 'image',q,int(item.get('width') or 0),int(item.get('height') or 0))
        bad_dl+=1
    if results: _probe(label,f"{len(results)} results, 0 usable (licence={bad_lic}, format={bad_ext}, download={bad_dl}{_dl_note(bad_dl)})")
    return None

def _wikimedia(q,video,w,h):
    label=f"Wikimedia {'video' if video else 'photo'}"
    typ='video' if video else 'bitmap'
    params={'action':'query','format':'json','generator':'search','gsrsearch':f'filetype:{typ} {q}','gsrnamespace':6,'gsrlimit':10,'prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':1920}
    # Commons can answer HTTP 200 with an error body (e.g.
    # cirrussearch-too-busy-error) — that is NOT "0 results". One retry for
    # transient ones, then name the error in the probe.
    payload = None
    for attempt in (1, 2):
        r=_http_get('https://commons.wikimedia.org/w/api.php',params=params,headers={'User-Agent':_UA_API})
        if not r: _probe(label,_req_fail()); return None
        try: payload = r.json() or {}
        except Exception as exc:
            _probe(label,f"api error: non-JSON response ({' '.join(str(exc).split())[:120]})"); return None
        err = payload.get('error')
        if not err: break
        code = str(err.get('code') or 'unknown')
        if attempt == 1 and ('too-busy' in code or 'ratelimit' in code or 'timeout' in code):
            time.sleep(2.0); continue
        _probe(label,f"api error: {code}"); return None
    pages=list(((payload.get('query') or {}).get('pages') or {}).values())
    if not pages: _probe(label,"0 results")
    pages.sort(key=lambda p:_aspect_rank((p.get('imageinfo') or [{}])[0],w,h))
    bad_media=bad_ext=bad_lic=bad_dl=0
    for page in pages:
        info=(page.get('imageinfo') or [{}])[0]; mime=info.get('mime') or ''
        if (video and not mime.startswith('video/')) or (not video and not mime.startswith('image/')):
            bad_media+=1; continue
        meta=info.get('extmetadata') or {}; lic=(meta.get('LicenseShortName') or {}).get('value','see Commons page'); lic_norm=str(lic).lower()
        if any(term in lic_norm for term in ('noncommercial','non-commercial','share alike','share-alike','no derivatives','no-derivatives')) \
           or not any(term in lic_norm for term in ('cc0','public domain','cc by','cc-by')):
            bad_lic+=1; continue
        # Photos: Commons has already rendered a 1920px JPEG for the file
        # (iiurlwidth above) — download THAT. Originals are frequently 100+ MB
        # TIFFs that bust the size cap or the 30s timeout; the only candidate
        # for one scene died exactly there. Videos have no usable thumbnail —
        # their thumburl is a still frame — so they keep the source file.
        src=info.get('url') if video else (info.get('thumburl') or info.get('url'))
        ext=Path(urlparse(src or '').path).suffix.lstrip('.') or ('webm' if video else 'jpg')
        if not src or ext.lower() not in ({'mp4','webm','ogv','ogg','mov'} if video else {'jpg','jpeg','png','webp','tif','tiff'}):
            bad_ext+=1; continue
        dest=_cache_path('wikimedia',page.get('title',src),ext)
        if _download(src,dest):
            creator=(meta.get('Artist') or {}).get('value','creator not listed')
            note=f'Wikimedia Commons — {lic}; creator: {creator}; attribution required, verify file page'
            _probe(label,"ok")
            return Asset(dest,'wikimedia',info.get('descriptionurl',''),note,'video' if video else 'image',q,int(info.get('width') or 0),int(info.get('height') or 0))
        bad_dl+=1
    if pages: _probe(label,f"{len(pages)} results, 0 usable (media={bad_media}, format={bad_ext}, licence={bad_lic}, download={bad_dl}{_dl_note(bad_dl)})")
    return None

def _internet_archive(q,video,w,h):
    """Internet Archive: use only items with explicit CC or public-domain rights."""
    label=f"Internet Archive {'video' if video else 'photo'}"
    media='movies' if video else 'image'
    r=_http_get('https://archive.org/advancedsearch.php',params={
        'q':f'mediatype:{media} AND ({q})','fl[]':['identifier','title','licenseurl'],
        'rows':8,'page':1,'output':'json'})
    if not r: _probe(label,_req_fail()); return None
    docs=(r.json().get('response') or {}).get('docs',[])
    if not docs: _probe(label,"0 results")
    bad_lic=bad_files=bad_dl=0
    for doc in docs:
        ident=doc.get('identifier')
        if not ident:continue
        m=_http_get('https://archive.org/metadata/'+quote(str(ident),safe=''))
        if not m:continue
        metadata=m.json().get('metadata') or {}; lic=doc.get('licenseurl') or metadata.get('licenseurl') or ''
        lic=str(lic).lower()
        if any(x in lic for x in ('-nc','/by-sa/','-nd','noncommercial')) \
           or not any(x in lic for x in ('creativecommons.org/licenses/by/','creativecommons.org/publicdomain/','creativecommons.org/zero/')):
            bad_lic+=1; continue  # never assume that an Archive item is reusable
        files=m.json().get('files') or []
        if video:
            choices=[f for f in files if 'mpeg4' in str(f.get('format','')).lower() and str(f.get('name','')).lower().endswith('.mp4')]
        else:
            choices=[f for f in files if 'jpeg' in str(f.get('format','')).lower() and str(f.get('name','')).lower().endswith(('.jpg','.jpeg'))]
        choices=[f for f in choices if int(f.get('size') or 0)<=120*1024*1024]
        if not choices:
            bad_files+=1; continue
        choices.sort(key=lambda f:(abs(int(f.get('width') or 0)/max(1,int(f.get('height') or 1))-w/max(1,h)), -int(f.get('size') or 0)))
        file=choices[0]; name=str(file.get('name','')); ident_url=quote(str(ident),safe=''); name_url=quote(name,safe='/')
        url=f'https://archive.org/download/{ident_url}/{name_url}'
        ext=Path(name).suffix.lstrip('.').lower() or ('mp4' if video else 'jpg'); dest=_cache_path('internetarchive',f'{ident}:{name}',ext)
        if _download(url,dest):
            kind='video' if video else 'image'; creator=metadata.get('creator','creator not listed')
            _probe(label,"ok")
            return Asset(dest,'internetarchive',f'https://archive.org/details/{ident}',f'Internet Archive — explicit license {lic}; creator: {creator}; verify item metadata',kind,q,int(file.get('width') or 0),int(file.get('height') or 0))
        bad_dl+=1
    if docs: _probe(label,f"{len(docs)} results, 0 usable (licence={bad_lic}, no-file={bad_files}, download={bad_dl}{_dl_note(bad_dl)})")
    return None

def _nasa(q,video,w,h):
    label=f"NASA {'video' if video else 'photo'}"
    media="video" if video else "image"; r=_http_get("https://images-api.nasa.gov/search",params={"q":q,"media_type":media})
    if not r: _probe(label,_req_fail()); return None
    items=((r.json().get("collection") or {}).get("items") or [])[:8]
    if not items: _probe(label,"0 results")
    bad_url=bad_dl=0
    for item in items:
        data=(item.get("data") or [{}])[0]
        if video:
            m=_http_get(item.get("href",""))
            if not m: bad_url+=1; continue
            urls=m.json() if "json" in m.headers.get("content-type","") else []
            url=next((u for u in urls if str(u).lower().endswith(".mp4")),None)
        else:
            url=next((x.get("href") for x in (item.get("links") or []) if x.get("render")=="image"),None)
        if not url:
            bad_url+=1; continue
        ext="mp4" if video else (Path(urlparse(url).path).suffix.lstrip(".") or "jpg"); dest=_cache_path("nasa",data.get("nasa_id",url),ext)
        if _download(url,dest):
            _probe(label,"ok")
            return Asset(dest,"nasa",item.get("href",""),"NASA media — public domain; credit NASA and check for third-party material","video" if video else "image",q,int(data.get("width") or 0),int(data.get("height") or 0))
        bad_dl+=1
    if items: _probe(label,f"{len(items)} results, 0 usable (no-media={bad_url}, download={bad_dl}{_dl_note(bad_dl)})")
    return None

def _title_card(query,scene_no,out_dir,title=""):
    from .textplates import render_text_plate
    out_dir.mkdir(parents=True,exist_ok=True); dest=out_dir/f"card_{scene_no:02d}_{_slugify(query)[:24]}.png"
    palette=[(22,33,62),(15,52,96),(83,52,131),(27,67,50),(61,43,31)]; color=palette[scene_no%len(palette)]
    try:render_text_plate(dest,title=title or query,subtitle=f"Scene {scene_no//10}",bg_color=color,title_size=42)
    except Exception:
        from PIL import Image
        Image.new("RGB",(CONFIG.width,CONFIG.height),color).save(dest)
    return Asset(dest,"generated","n/a (generated placeholder)","generated","image",query,CONFIG.width,CONFIG.height)

def fetch_scene_assets(query,scene_no,out_dir,count=None,target_width=None,target_height=None,allow_generated=False):
    """Free platform search, globally video-first then photo; never fabricates a source."""
    count=count or CONFIG.clips_per_scene; w=target_width or CONFIG.width; h=target_height or CONFIG.height
    out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True); q=query.strip() or "cinematic documentary"
    videos=[("Pexels video",lambda:_pexels(q,True,w,h)),("Pixabay video",lambda:_pixabay(q,True,w,h))]
    photos=[("Pexels photo",lambda:_pexels(q,False,w,h)),("Pixabay photo",lambda:_pixabay(q,False,w,h))]
    if CONFIG.enable_keyless_sources:
        # Openverse is photos-only here: its /v1/videos/ endpoint does not
        # exist (permanently 404, verified 2026-10-21), so keyless video is
        # Wikimedia / Internet Archive / NASA only.
        videos += [("Wikimedia video",lambda:_wikimedia(q,True,w,h)),("Internet Archive video",lambda:_internet_archive(q,True,w,h)),("NASA video",lambda:_nasa(q,True,w,h))]
        photos += [("Openverse photo",lambda:_openverse(q,False,w,h)),("Wikimedia photo",lambda:_wikimedia(q,False,w,h)),("Internet Archive photo",lambda:_internet_archive(q,False,w,h)),("NASA photo",lambda:_nasa(q,False,w,h))]
    assets=[]; attempts=[]
    for i in range(count):
        got=None
        for name,fn in videos+photos:
            _PROBE.pop(name,None)  # never inherit a previous iteration's detail
            try:got=fn()
            except Exception as exc:
                print(f"[assets] source {name} errored: {exc!r}", flush=True); got=None
                detail=f"error: {exc}"
            else:detail="ok" if got else (_PROBE.get(name) or "no match")
            if got:status="ok"
            elif detail=="no API key":status="skipped"
            elif detail.startswith("error:"):status="error"
            else:status="miss"
            if not any(a["provider"]==name and a["status"]==status and a["detail"]==detail for a in attempts):
                attempts.append({"provider":name,"status":status,"detail":detail})
            print(f"[assets] scene {scene_no}: {name} → {status}" + (f" ({detail})" if status!="ok" else ""), flush=True)
            if got:
                got.query=q; assets.append(got); print(f"[assets] scene {scene_no}: {got.kind} from {got.source} ({got.width}x{got.height})"); break
        if not got:
            if allow_generated:assets.append(_title_card(q,scene_no*10+i,out_dir,title=q))
            else:break
    _write_attempts(out_dir,scene_no,attempts)
    if assets:_write_credits(out_dir,assets)
    return assets

def _write_attempts(out_dir,scene_no,attempts):
    """Persist per-provider attempt outcomes so a failed scene can explain itself."""
    path=Path(out_dir)/"sourcing-attempts.json"
    try:data=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:data={}
    data[str(scene_no)]=attempts
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    except Exception as exc:print(f"[assets] could not write attempts report: {exc!r}")

def attempts_summary(scene_no,assets_dir):
    """One-line digest of a failed scene's attempts for the error message (CI annotation)."""
    path=Path(assets_dir)/"sourcing-attempts.json"
    try:rows=json.loads(path.read_text(encoding="utf-8")).get(str(scene_no)) or []
    except Exception:return ""
    bits=[]
    for row in rows:
        if row.get("status")=="ok":continue
        detail=str(row.get("detail") or "")
        if detail in ("no match","ok"):detail=""
        bits.append(f"{row.get('provider')}={row.get('status')}" + (f": {detail}" if detail else ""))
    return (" | attempts: " + "; ".join(bits)) if bits else ""

def _write_credits(out_dir,assets):
    path=Path(out_dir)/"credits.json"
    try:existing=json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except Exception:existing=[]
    known={(x.get("source"),x.get("origin_url"),x.get("query")) for x in existing}
    for a in assets:
        d=asdict(a); d["path"]=str(a.path); key=(d["source"],d["origin_url"],d["query"])
        if key not in known:existing.append(d); known.add(key)
    path.write_text(json.dumps(existing,indent=2,ensure_ascii=False),encoding="utf-8")
