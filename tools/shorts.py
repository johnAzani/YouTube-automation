#!/usr/bin/env python3
"""Shorts assembler — 9:16 vertical twin of deep_dive v5.

Same documentary motion engine, reformatted for YouTube Shorts:

- 720x1280 @24fps (9:16 vertical), 1080x1920 super-sampled plates, sub-pixel camera
- Speech-locked scene cuts (every 4-6s), contain-fit media (full source frame, no crop/stretch)
- Clip-first free stock search (Pexels, Pixabay, Openverse, Commons, Internet Archive, NASA); story-photo fail-safe
- Word-sync motion graphics over image, non-overlapping hero beats (center-screen)
- Contextual viz diagrams, caption ribbon (near bottom, safe-area), tease cards,
  cold open + HUD + progress bar + end CTA — all re-laid for vertical
- Score-only audio (voice + background music, zero SFX), hush/swell automation

Run: .venv/bin/python tools/shorts.py [short-johnstown|short-enron]
"""
import os, sys, json, math, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import generate_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)  # shared pipeline source adapters
# Authored-still licence ledger. Falls back to the old blanket string if the pipeline
# package is unavailable, so a bookkeeping module can never break a render.
try:
    from pipeline.licences import licence_note as LICENCE_NOTE, licence_report as LICENCE_REPORT
except Exception:  # pragma: no cover - import guard only
    LICENCE_NOTE = lambda name: ('pre-existing image-search still; source/license metadata '
                                 'unavailable in current ledger — verify before monetized reuse')
    LICENCE_REPORT = lambda names: []
W, H, FPS = 720, 1280, 24
CW, CH = 1080, 1920  # 1.5x super-sampled plate canvas for sub-pixel camera (9:16)

NAVY = (6, 26, 51)
YELLOW = (255, 201, 60)
CRIMSON = (255, 86, 92)
EMERALD = (72, 232, 164)
WHITE = (255, 255, 255)
FAINT = (122, 156, 202)
ICE = (170, 210, 248)

FFMPEG = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
FDIR = os.path.join(ROOT, 'assets', 'fonts')
IMG = os.path.join(ROOT, 'image-search')
AUDIO = os.path.join(ROOT, 'assets', 'deepdive')

FONT_CACHE = {}
def fnt(w, sz):
    k = (w, int(sz))
    if k not in FONT_CACHE:
        FONT_CACHE[k] = ImageFont.truetype(os.path.join(FDIR, f'Inter-{w}.ttf'), int(sz))
    return FONT_CACHE[k]

# ---------------------------------------------------------------- easing ----
def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))
def ease_out_expo(x):
    x = clamp01(x); return 1.0 if x >= 1.0 else 1.0 - 2.0 ** (-10.0 * x)
def ease_out_cubic(x):
    x = clamp01(x); return 1.0 - (1.0 - x) ** 3
def ease_in_out_sine(x):
    x = clamp01(x); return 0.5 - 0.5 * math.cos(math.pi * x)
def ease_out_back(x):
    x = clamp01(x); c1, c3 = 1.70158, 2.70158; return 1.0 + c3 * (x - 1.0) ** 3 + c1 * (x - 1.0) ** 2

def duration(path):
    r = subprocess.run([FFMPEG, '-i', path], capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if 'Duration:' in ln:
            hh, mm, rest = ln.split('Duration: ')[1].split(',')[0].strip().split(':')
            return int(hh)*3600 + int(mm)*60 + float(rest)
    raise SystemExit(f'no duration for {path}')

# -------------------------------------- blue grade + vertical plate ----
def _duotone_luts():
    shadow, mid, high = (3,11,32),(14,52,114),(176,214,250)
    lr,lg,lb=[],[],[]
    for i in range(256):
        t=i/255.0
        if t<0.55:
            u=t/0.55; c=[shadow[k]+(mid[k]-shadow[k])*u for k in range(3)]
        else:
            u=(t-0.55)/0.45; c=[mid[k]+(high[k]-mid[k])*(u**1.12) for k in range(3)]
        lr.append(int(c[0])); lg.append(int(c[1])); lb.append(int(c[2]))
    return lr,lg,lb
LUT_R,LUT_G,LUT_B=_duotone_luts()
def grade_blue(im, tint_warm=0.0):
    rgb=im.convert('RGB'); lum=rgb.convert('L')
    duo=Image.merge('RGB',(lum.point(LUT_R),lum.point(LUT_G),lum.point(LUT_B)))
    out=Image.blend(rgb,duo,0.82)
    if tint_warm>0:
        warm=Image.merge('RGB',(lum.point(lambda v:min(255,int(v*1.25))),lum.point(lambda v:int(v*0.68)),lum.point(lambda v:int(v*0.28))))
        out=Image.blend(out,warm,tint_warm)
    return out.point(lambda v:max(0,min(255,int(128+(v-128)*1.14))))
def vignette():
    v=Image.new('L',(W,H),0); d=ImageDraw.Draw(v)
    d.ellipse([-W*0.30,-H*0.12,W*1.30,H*1.12],fill=255)
    return v.filter(ImageFilter.GaussianBlur(90))
VIG=vignette()
VIG_DARK=Image.new('RGB',(W,H),(2,7,20))
def prep_plate(path, focus_side=0.0, tint_warm=0.0):
    """Build a portrait cinematic plate with the complete source frame intact.

    Contain-fit the original into an inset 84% safe window: no crop, no stretch.
    The remaining canvas is a designed dark matte, not a zoomed/cropped duplicate.
    Camera moves can travel over the matte without cutting off the source image.
    """
    raw=Image.open(path).convert('RGB')
    fit=min((CW*.90)/max(1,raw.width),(CH*.90)/max(1,raw.height))
    raw=raw.resize((max(1,int(round(raw.width*fit))),max(1,int(round(raw.height*fit)))),Image.Resampling.LANCZOS)
    # Scene-adaptive radial matte uses sampled colour only, never a stretched or
    # cropped duplicate of the photograph. The complete source frame stays sharp.
    avg=Image.new('RGB',(1,1)); avg.paste(raw.resize((1,1),Image.Resampling.BILINEAR))
    ar,ag,ab=avg.getpixel((0,0)); glow_col=(min(30,int(ar*.12)),min(52,int(ag*.18)),min(92,int(ab*.24)))
    canvas=Image.new('RGB',(CW,CH),(4,12,29))
    glow=Image.new('RGB',(CW,CH),(0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse((CW*.04,CH*.10,CW*.96,CH*.90),fill=glow_col)
    glow=glow.filter(ImageFilter.GaussianBlur(145))
    canvas=Image.blend(canvas,glow,0.82)
    x=(CW-raw.width)//2; y=(CH-raw.height)//2
    # Low-opacity edge light, then the untouched full-frame media plate.
    shadow=Image.new('RGBA',(CW,CH),(0,0,0,0)); sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x-5,y-5,x+raw.width+5,y+raw.height+5),radius=14,fill=(0,0,0,170),outline=(120,180,240,110),width=2)
    shadow=shadow.filter(ImageFilter.GaussianBlur(8)); canvas=Image.alpha_composite(canvas.convert('RGBA'),shadow).convert('RGB')
    canvas.paste(raw,(x,y))
    canvas=canvas.filter(ImageFilter.UnsharpMask(radius=1.1,percent=95,threshold=3))
    return grade_blue(canvas,tint_warm=tint_warm)


def video_plate_reader(path):
    """Return an ffmpeg reader that streams contain-fitted 9:16 RGB frames."""
    # Source is scaled proportionally into a conservative 84% safe window. The
    # full input frame remains visible, regardless of its aspect ratio.
    sw,sh=int(CW*.90),int(CH*.90)
    vf=(f'scale={sw}:{sh}:force_original_aspect_ratio=decrease,setsar=1,'
        f'pad={CW}:{CH}:(ow-iw)/2:(oh-ih)/2:color=0x061a33,fps={FPS},format=rgb24')
    cmd=[FFMPEG,'-loglevel','error','-stream_loop','-1','-i',str(path),'-an','-vf',vf,'-f','rawvideo','-pix_fmt','rgb24','pipe:1']
    return subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=10**7)


def read_video_plate(proc):
    if not proc or proc.stdout is None: return None
    size=CW*CH*3; data=bytearray()
    while len(data)<size:
        chunk=proc.stdout.read(size-len(data))
        if not chunk: return None
        data.extend(chunk)
    return grade_blue(Image.frombytes('RGB',(CW,CH),bytes(data)))


def stop_video_plate(proc):
    if not proc:return
    if proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=2)
    if proc.stdout:
        try: proc.stdout.close()
        except OSError: pass

# --------------------------------------- sub-pixel smooth camera movement ----
def camera_frame(plate, p, mode='push_in', focus=(0.5,0.42), extra_zoom=1.0):
    p=clamp01(p); s=0.65*ease_in_out_sine(p)+0.35*p; fx,fy=focus
    # Camera travel is deliberately bounded inside the 90% source-safe matte:
    # movement remains perceptible, while the original frame never gets clipped.
    if mode=='push_in':
        z=1.0+0.045*s; dx=(fx-0.5)*0.035*s; dy=(fy-0.5)*0.025*s
    elif mode=='pull_out':
        z=1.045-0.045*s; dx=(fx-0.5)*0.03*(1.0-s); dy=(fy-0.5)*0.02*(1.0-s)
    elif mode=='pan_right':
        z=1.025+0.015*s; dx=-0.0125+0.025*s; dy=(fy-0.5)*0.02*s
    elif mode=='pan_left':
        z=1.025+0.015*s; dx=0.0125-0.025*s; dy=(fy-0.5)*0.02*s
    elif mode=='tilt_up':
        z=1.025+0.015*s; dx=(fx-0.5)*0.02*s; dy=0.01-0.02*s
    else:
        z=1.005+0.035*s; dx=0.006*math.sin(p*math.pi); dy=-0.012*s
    z*=extra_zoom
    dx+=0.00035*math.sin(p*6.1+1.3); dy+=0.0003*math.sin(p*4.3+2.7); z*=1.0+0.001*math.sin(p*2.4+0.6)
    vw=CW/z; vh=CH/z; cx=CW*(0.5+dx); cy=CH*(0.5+dy)
    x0=max(0.0,min(CW-vw,cx-vw*0.5)); y0=max(0.0,min(CH-vh,cy-vh*0.5))
    im=plate.transform((W,H),Image.EXTENT,(x0,y0,x0+vw,y0+vh),Image.BICUBIC)
    return Image.composite(im,VIG_DARK,VIG)

def optical_flare_transition(f_prev, f_curr, u):
    e=ease_in_out_sine(u); base=Image.blend(f_prev,f_curr,e)
    inten=math.sin(clamp01(u)*math.pi)**1.6
    if inten<=0.02: return base
    flare=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(flare)
    cy=int(H*0.50); band_h=int(95*inten+12); a_core=int(72*inten)
    d.ellipse([-120,cy-band_h,W+120,cy+band_h],fill=(165,215,255,a_core))
    d.rectangle([0,cy-3,W,cy+3],fill=(255,225,130,int(90*inten)))
    flare=flare.filter(ImageFilter.GaussianBlur(18))
    return Image.alpha_composite(base.convert('RGBA'),flare).convert('RGB')

# ------------------------------------------------------------- glass cards ----
GLASS_CACHE={}
def glass_card(w,h,radius=18,top=(12,42,92),bot=(5,20,52),a_top=222,a_bot=188,border_col=(126,184,255,165)):
    w,h=max(16,int(w)),max(16,int(h))
    key=(w,h,radius,top,bot,a_top,a_bot,border_col)
    if key in GLASS_CACHE: return GLASS_CACHE[key]
    S=2
    mask=Image.new('L',(w*S,h*S),0); ImageDraw.Draw(mask).rounded_rectangle([0,0,w*S-1,h*S-1],radius=radius*S,fill=255)
    grad=Image.new('RGBA',(w*S,h*S),(0,0,0,0)); gd=ImageDraw.Draw(grad)
    for y in range(h*S):
        u=y/max(1,h*S-1); col=tuple(int(top[k]+(bot[k]-top[k])*u) for k in range(3))
        gd.line([(0,y),(w*S,y)],fill=col+(int(a_top+(a_bot-a_top)*u),))
    card=Image.new('RGBA',(w*S,h*S),(0,0,0,0)); card.paste(grad,(0,0),mask)
    bd=ImageDraw.Draw(card); bd.rounded_rectangle([1,1,w*S-2,h*S-2],radius=radius*S,outline=border_col,width=3)
    card=card.resize((w,h),Image.LANCZOS)
    d=ImageDraw.Draw(card); d.line([(radius,1),(w-radius,1)],fill=(210,234,255,110),width=1)
    GLASS_CACHE[key]=card; return card
def card_alpha(card,a):
    a=clamp01(a)
    if a>=0.999: return card
    c=card.copy(); c.putalpha(c.getchannel('A').point(lambda v:int(v*a))); return c

# -------------------------------------------------------------- text engine ----
def tracked_width(d,text,font,tracking):
    if not text: return 0.0
    return sum(d.textlength(ch,font=font)+tracking for ch in text)-tracking
def draw_tracked(d,text,font,x,y,fill,tracking=3.0):
    for ch in text:
        d.text((x,y),ch,font=font,fill=fill); x+=d.textlength(ch,font=font)+tracking
def kinetic_line(layer,text,font,cx,y,t,t0,color=WHITE,tracking=3.0,stagger=0.04,dur=0.48,slide=32,bounce=False,out_a=1.0):
    if out_a<=0.01: return
    d=ImageDraw.Draw(layer); w=tracked_width(d,text,font,tracking); x=cx-w/2.0
    for i,ch in enumerate(text):
        local=clamp01((t-t0-i*stagger)/dur)
        if local<=0: x+=d.textlength(ch,font=font)+tracking; continue
        e=ease_out_back(local) if bounce else ease_out_expo(local)
        a=int(255*min(1.0,local*1.9)*out_a); yy=y+(1.0-e)*slide
        if local<0.96: d.text((x,yy+(1.0-e)*slide*0.45),ch,font=font,fill=color+(a//3,))
        d.text((x,yy),ch,font=font,fill=color+(a,)); x+=d.textlength(ch,font=font)+tracking
def fit_font(weight,sz,text,maxw,tracking=2.5):
    f=fnt(weight,sz); d=ImageDraw.Draw(Image.new('RGB',(8,8)))
    while tracked_width(d,text,f,tracking)>maxw and sz>14:
        sz=int(sz*0.92); f=fnt(weight,sz)
    return f

# ------------------------------------------------ cold-open & end overlays (vertical) ----
def cold_open_overlay(layer, title_pair, t, dur=4.0):
    if t<0 or t>dur: return
    in_e=ease_out_expo(clamp01(t/0.55))
    out_a=1.0 if t<dur-0.55 else 1.0-ease_in_out_sine((t-(dur-0.55))/0.55)
    a=in_e*out_a
    if a<=0.01: return
    t1,t2=title_pair
    f1=fit_font('Black',38,t1,W-48,2.6)
    f2=fnt('SemiBold',14)
    d=ImageDraw.Draw(layer)
    w1=tracked_width(d,t1,f1,2.6)
    pw=int(min(W-32,max(w1+64,460))); ph=132
    px=W//2-pw//2; py=int(210 -(1.0-in_e)*24)
    layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=18,a_top=225,a_bot=195),a),(px,py))
    bw=int(110*ease_out_back(clamp01((t-0.10)/0.5)))
    d.rectangle([W//2-bw//2,py+18,W//2+bw//2,py+22],fill=YELLOW+(int(240*a),))
    kinetic_line(layer,t1,f1,W/2,py+32,t,0.06,WHITE,2.6,stagger=0.026,dur=0.42,slide=20,out_a=a)
    w2=tracked_width(d,t2,f2,3.2)
    sa=int(235*clamp01((t-0.35)/0.45)*a)
    if sa>0: draw_tracked(d,t2,f2,W/2-w2/2,py+92,ICE+(sa,),3.2)

def end_card_overlay(base_img, end_pair, t_local, T):
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    e=ease_out_expo(clamp01(t_local/0.5))
    dim=Image.new('RGBA',(W,H),(3,12,28,int(165*e)))
    layer=Image.alpha_composite(layer,dim)
    t1,t2=end_pair
    pw,ph=580,200; px,py=(W-pw)//2,(H-ph)//2 - 30
    layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=22,a_top=235,a_bot=205,border_col=YELLOW+(190,)),e),(px,py))
    d=ImageDraw.Draw(layer)
    f1=fnt('Black',44); f2=fit_font('SemiBold',17,t2.upper(),pw-60,3.0)
    kinetic_line(layer,t1,f1,W/2,py+28,t_local,0.05,YELLOW,3.2,stagger=0.04,dur=0.45,slide=24,bounce=True,out_a=e)
    bw=int(160*ease_out_back(clamp01((t_local-0.25)/0.5)))
    d.rectangle([W//2-bw//2,py+98,W//2+bw//2,py+102],fill=WHITE+(int(220*e),))
    w2=tracked_width(d,t2.upper(),f2,3.0)
    sa=int(240*clamp01((t_local-0.30)/0.45))
    if sa>0: draw_tracked(d,t2.upper(),f2,W/2-w2/2,py+124,ICE+(sa,),3.0)
    return Image.alpha_composite(base_img.convert('RGBA'),layer).convert('RGB')

# -------------------------------------- HUD + chapter badge + word ribbon (vertical) ----
def hud_chapter_layer(kicker, sub, idx, nscenes, t_scene, scene_dur, total_frac):
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    in_e=ease_out_expo(clamp01(t_scene/0.45))
    out_e=1.0 if (scene_dur-t_scene)>0.35 else clamp01((scene_dur-t_scene)/0.35)
    a=in_e*out_e
    if a>0.02:
        fk=fnt('Bold',13); fs=fnt('Medium',11); fc=fnt('Black',11)
        d=ImageDraw.Draw(layer)
        tag=f'CH {idx:02d}/{nscenes:02d}'
        wk=tracked_width(d,kicker,fk,1.4); ws=tracked_width(d,sub,fs,1.6) if sub else 0
        cw=int(max(wk+108,ws+108, 280)); ch=52 if sub else 38
        cx,cy=int(14 -(1.0-in_e)*24),18
        layer.alpha_composite(card_alpha(glass_card(cw,ch,radius=12,a_top=210,a_bot=175),a),(cx,cy))
        d.rounded_rectangle([cx+10,cy+8,cx+78,cy+28],radius=6,fill=YELLOW+(int(240*a),))
        wt=d.textlength(tag,font=fc)
        d.text((cx+44-wt/2,cy+10),tag,font=fc,fill=NAVY+(int(255*a),))
        draw_tracked(d,kicker,fk,cx+88,cy+8,WHITE+(int(250*a),),1.4)
        if sub: draw_tracked(d,sub,fs,cx+88,cy+28,ICE+(int(215*a),),1.6)
    # Top-right shorts progress pill (compact)
    d=ImageDraw.Draw(layer)
    pw,ph=120,28; px,py=W-pw-14,18
    layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14,a_top=195,a_bot=160),0.92),(px,py))
    fp=fnt('Bold',11); pct=f'{int(clamp01(total_frac)*100):3d}%'
    d.text((px+12,py+7),'DOC',font=fp,fill=ICE+(210,))
    d.rectangle([px+44,py+11,px+84,py+16],fill=(255,255,255,45))
    fill_w=int(40*clamp01(total_frac))
    if fill_w>0: d.rectangle([px+44,py+11,px+44+fill_w,py+16],fill=YELLOW+(240,))
    d.text((px+88,py+7),pct,font=fp,fill=WHITE+(235,))
    # Bottom progress bar (thicker for Shorts thumb)
    d.rectangle([0,H-6,W,H],fill=(255,255,255,32))
    bx=int(W*clamp01(total_frac))
    if bx>0: d.rectangle([0,H-6,bx,H],fill=YELLOW+(235,))
    return layer

def build_caption_stream(key, raw_words):
    clauses=SCRIPTS[key]['captions']; stream=[]
    for i0,i1,text in clauses:
        seg=raw_words[i0:i1+1]; t_start,t_end=seg[0][0],seg[-1][1]
        cwords=text.split(); n=len(cwords)
        if n==len(seg):
            w_entries=[(seg[j][0],seg[j][1],cwords[j]) for j in range(n)]
        else:
            weights=[max(2,len(w)) for w in cwords]; tot_w=float(sum(weights)); cur=t_start; w_entries=[]
            for w,wt in zip(cwords,weights):
                dt=(t_end-t_start)*(wt/tot_w); w_entries.append((cur,cur+dt,w)); cur+=dt
        stream.append(dict(t0=t_start,t1=t_end,words=w_entries))
    return stream

def caption_ribbon_layer(stream, t):
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    active=None
    for c in stream:
        if c['t0']-0.12<=t<=c['t1']+0.18: active=c; break
    if not active: return layer
    in_a=clamp01((t-(active['t0']-0.12))/0.16); out_a=clamp01(((active['t1']+0.18)-t)/0.18); a=min(in_a,out_a)
    if a<=0.02: return layer
    # Vertical: slightly smaller font, centered, near bottom safe area
    f=fnt('ExtraBold',19); d=ImageDraw.Draw(layer); gap=7.0
    words=active['words']
    widths=[d.textlength(w.upper(),font=f) for _,_,w in words]
    total_w=sum(widths)+gap*max(0,len(words)-1)
    if total_w>W-28:
        f=fnt('ExtraBold',16); widths=[d.textlength(w.upper(),font=f) for _,_,w in words]
        total_w=sum(widths)+gap*max(0,len(words)-1)
        if total_w>W-28:
            f=fnt('ExtraBold',14); widths=[d.textlength(w.upper(),font=f) for _,_,w in words]
            total_w=sum(widths)+gap*max(0,len(words)-1)
    pw=int(total_w+32); ph=44; px=W//2-pw//2; py=H-200
    layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=12,top=(6,22,52),bot=(3,12,30),a_top=232,a_bot=215),a),(px,py))
    cur_idx=0
    for j,(ws,we,_) in enumerate(words):
        if t>=ws-0.04: cur_idx=j
    x=W/2.0-total_w/2.0
    for j,((ws,we,w),ww) in enumerate(zip(words,widths)):
        txt=w.upper()
        if j==cur_idx:
            pad_x=5; d.rounded_rectangle([x-pad_x,py+7,x+ww+pad_x,py+ph-7],radius=7,fill=(255,201,60,int(48*a)),outline=(255,201,60,int(145*a)),width=1)
            d.text((x,py+10),txt,font=f,fill=YELLOW+(int(255*a),))
        elif j<cur_idx: d.text((x,py+11),txt,font=f,fill=WHITE+(int(240*a),))
        else: d.text((x,py+11),txt,font=f,fill=ICE+(int(155*a),))
        x+=ww+gap
    return layer

# ------------------------- contextual visual diagrams (viz_layer) — vertical ----
def viz_layer(viz_kind, t_scene, scene_dur):
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    if not viz_kind: return layer
    in_e=ease_out_expo(clamp01((t_scene-0.15)/0.5)); out_a=1.0 if (scene_dur-t_scene)>0.45 else clamp01((scene_dur-t_scene)/0.45); a=in_e*out_a
    if a<=0.02: return layer
    prog=clamp01((t_scene-0.15)/1.65); d=ImageDraw.Draw(layer)

    if viz_kind=='pressure_gauge':
        pw,ph,px,py=360,108, W//2-180, 640
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12); f2=fnt('Black',14)
        d.text((px+16,py+12),'HYDROSTATIC DAM LOAD',font=f1,fill=ICE+(int(230*a),))
        d.rectangle([px+16,py+36,px+pw-16,py+58],fill=(255,255,255,int(38*a)))
        bw=int((pw-32)*ease_out_expo(prog)); col=CRIMSON if prog>0.75 else YELLOW
        if bw>2: d.rectangle([px+16,py+36,px+16+bw,py+58],fill=col+(int(240*a),))
        d.text((px+16,py+72),'EARTHEN CREST: CRITICAL',font=f1,fill=col+(int(245*a),))

    elif viz_kind=='dam_anatomy':
        pw,ph,px,py=420,170,W//2-210,620
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        fh=fnt('Black',13); fb=fnt('SemiBold',12)
        d.text((px+16,py+12),'FATAL MODIFICATIONS TO DAM',font=fh,fill=YELLOW+(int(245*a),))
        items=[(0.08,'01  IRON SCREENS CLOG PIPES'),(0.32,'02  SPILLWAY CHOKED'),(0.56,'03  CREST LOWERED 3FT')]
        for idx,(thr,txt) in enumerate(items):
            ia=clamp01((prog-thr)/0.25)*a
            if ia>0.02:
                yy=py+38+idx*38
                d.rounded_rectangle([px+16,yy,px+pw-16,yy+30],radius=8,fill=(255,86,92,int(45*ia)),outline=CRIMSON+(int(160*ia),),width=1)
                d.text((px+26,yy+7),txt,font=fb,fill=WHITE+(int(245*ia),))

    elif viz_kind=='rain_rising':
        for r in range(22):
            rx=int(((r*137+t_scene*420)%(W+100))-50); ry=int(((r*91+t_scene*780)%(H+120))-60)
            d.line([(rx,ry),(rx-10,ry+32)],fill=(185,220,255,int(70*a)),width=2)
        pw,ph,px,py=340,120,W//2-170,680
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12)
        d.text((px+16,py+12),'RESERVOIR WATER LEVEL',font=f1,fill=ICE+(int(235*a),))
        d.rectangle([px+16,py+36,px+pw-16,py+62],outline=ICE+(int(140*a),),width=2)
        fill_w=int((pw-36)*ease_out_cubic(prog)); col=CRIMSON if prog>0.8 else YELLOW
        d.rectangle([px+18,py+38,px+18+fill_w,py+60],fill=col+(int(230*a),))
        d.text((px+16,py+76),'STATUS: OVERTOPPING CREST',font=f1,fill=CRIMSON+(int(245*a),))

    elif viz_kind=='valley_drop':
        pw,ph,px,py=400,135,W//2-200,680
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12); f2=fnt('SemiBold',10)
        d.text((px+16,py+10),'14-MILE VALLEY DROP',font=f1,fill=YELLOW+(int(245*a),))
        pts=[(px+22,py+42),(px+125,py+62),(px+240,py+88),(px+365,py+98)]
        d.line(pts,fill=ICE+(int(160*a),),width=3)
        wx=int(px+22+(365-22)*ease_in_out_sine(prog)); wy=int(py+42+(98-42)*ease_in_out_sine(prog))
        d.ellipse([wx-6,wy-6,wx+6,wy+6],fill=YELLOW+(int(255*a),))
        d.text((px+16,py+108),'SOUTH FORK (3:10 PM)',font=f2,fill=ICE+(int(220*a),))
        d.text((px+230,py+108),'JOHNSTOWN (4:07 PM)',font=f2,fill=WHITE+(int(240*a),))

    elif viz_kind=='wave_scale':
        pw,ph,px,py=360,150,W//2-180,680
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12); f2=fnt('Bold',10)
        d.text((px+16,py+10),'FLOOD WAVE SCALE',font=f1,fill=YELLOW+(int(245*a),))
        base_y=py+125
        bars=[('LOCOMOTIVE',14,ICE),('HOUSE',24,WHITE),('FLOOD',36,CRIMSON)]
        for idx,(lab,ft,col) in enumerate(bars):
            bx=px+28+idx*108; bh=int((ft/36.0)*72*ease_out_expo(clamp01((prog-idx*0.15)/0.55)))
            d.rectangle([bx,base_y-bh,bx+56,base_y],fill=col+(int(230*a),))
            d.text((bx+8,base_y-bh-14),f'{ft} FT',font=f2,fill=WHITE+(int(240*a),))
            d.text((bx,base_y+6),lab,font=f2,fill=ICE+(int(210*a),))

    elif viz_kind=='mtm_ledger':
        pw,ph,px,py=400,130,W//2-200,680
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12); f2=fnt('Black',13)
        d.text((px+16,py+10),'MARK-TO-MARKET ILLUSION',font=f1,fill=YELLOW+(int(245*a),))
        for yr in range(10):
            bx=px+16+yr*22; d.rectangle([bx,py+36,bx+16,py+74],fill=(120,175,240,int(185*a)),outline=WHITE+(int(120*a),))
        d.text((px+16,py+84),'10-YR PROJECTION',font=fnt('SemiBold',10),fill=ICE+(int(220*a),))
        if prog>0.25:
            pa=clamp01((prog-0.25)/0.4)*a
            d.rounded_rectangle([px+230,py+32,px+380,py+82],radius=8,fill=(255,201,60,int(55*pa)),outline=YELLOW+(int(230*pa),),width=2)
            d.text((px+244,py+42),'BOOKED DAY 1',font=f2,fill=YELLOW+(int(250*pa),))
            d.text((px+244,py+60),'AS PROFIT',font=fnt('Bold',11),fill=WHITE+(int(245*pa),))

    elif viz_kind=='stock_boom':
        pw,ph,px,py=380,140,W//2-190,700
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12); f2=fnt('Black',18)
        d.text((px+16,py+10),'NYSE: ENE · SHARE PRICE',font=f1,fill=ICE+(int(235*a),))
        vals=[0.18,0.24,0.31,0.42,0.39,0.55,0.68,0.79,0.92,1.00]
        n_pts=max(2,int(len(vals)*ease_out_cubic(prog))); pts=[]
        for idx in range(n_pts):
            vx=px+18+idx*((pw-36)/(len(vals)-1)); vy=py+110-vals[idx]*62; pts.append((vx,vy))
        if len(pts)>=2:
            d.line(pts,fill=EMERALD+(int(245*a),),width=3); lx,ly=pts[-1]
            d.ellipse([lx-6,ly-6,lx+6,ly+6],fill=YELLOW+(int(255*a),))
            cur_p=18.0+(90.75-18.0)*vals[n_pts-1]
            d.text((px+pw-92,py+10),f'${cur_p:0.2f}',font=f2,fill=EMERALD+(int(250*a),))

    elif viz_kind=='shell_maze':
        pw,ph,px,py=420,130,W//2-210,680
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12); f2=fnt('Black',11)
        d.text((px+16,py+10),'OFF-BALANCE-SHEET SHELL MAZE',font=f1,fill=YELLOW+(int(245*a),))
        nodes=['ENRON','LJM 1&2','RAPTOR','CHEWCO']
        for idx,nm in enumerate(nodes):
            na=clamp01((prog-idx*0.16)/0.3)*a
            if na>0.02:
                nx=px+14+idx*100; ny=py+34
                col=CRIMSON if idx>0 else ICE
                d.rounded_rectangle([nx,ny,nx+88,ny+40],radius=8,fill=(20,45,90,int(220*na)),outline=col+(int(220*na),),width=2)
                d.text((nx+8,ny+12),nm,font=f2,fill=WHITE+(int(250*na),))
        d.text((px+16,py+90),'RESULT: $30B+ LOSSES HIDDEN',font=fnt('Bold',11),fill=CRIMSON+(int(245*a),))

    elif viz_kind=='insider_split':
        pw,ph,px,py=400,130,W//2-200,680
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        fb=fnt('Bold',12)
        d.rounded_rectangle([px+14,py+12,px+pw-14,py+58],radius=8,fill=(72,232,164,int(36*a)),outline=EMERALD+(int(180*a),),width=2)
        d.text((px+22,py+18),'MESSAGE TO STAFF:',font=fb,fill=EMERALD+(int(240*a),))
        d.text((px+22,py+32),'"KEEP BUYING ENRON"',font=fnt('Black',13),fill=WHITE+(int(250*a),))
        if prog>0.30:
            sa=clamp01((prog-0.30)/0.35)*a
            d.rounded_rectangle([px+14,py+66,px+pw-14,py+114],radius=8,fill=(255,86,92,int(48*sa)),outline=CRIMSON+(int(210*sa),),width=2)
            d.text((px+22,py+72),'EXECUTIVES DID:',font=fb,fill=CRIMSON+(int(245*sa),))
            d.text((px+22,py+88),'CASHED OUT $1.1B',font=fnt('Black',13),fill=YELLOW+(int(250*sa),))

    elif viz_kind=='stock_crash':
        pw,ph,px,py=380,140,W//2-190,700
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),a),(px,py))
        f1=fnt('Bold',12); f2=fnt('Black',18)
        d.text((px+16,py+10),'NYSE: ENE · COLLAPSE',font=f1,fill=ICE+(int(235*a),))
        vals=[1.0,0.88,0.74,0.58,0.42,0.28,0.15,0.06,0.01,0.003]
        n_pts=max(2,int(len(vals)*ease_out_cubic(prog))); pts=[]
        for idx in range(n_pts):
            vx=px+18+idx*((pw-36)/(len(vals)-1)); vy=py+110-vals[idx]*62; pts.append((vx,vy))
        if len(pts)>=2:
            d.line(pts,fill=CRIMSON+(int(250*a),),width=3); lx,ly=pts[-1]
            d.ellipse([lx-6,ly-6,lx+6,ly+6],fill=CRIMSON+(int(255*a),))
            cur_p=90.75*vals[n_pts-1]
            d.text((px+pw-92,py+10),f'${cur_p:0.2f}',font=f2,fill=CRIMSON+(int(250*a),))
    return layer

# ---------------------------------------------------------- word sync ----
def load_words(key):
    path=os.path.join(AUDIO,f'words-{key}.json')
    return json.load(open(path))
def find_phrase(words, phrase, occ=0):
    ws=phrase.split(); hits=[]
    for i in range(len(words)-len(ws)+1):
        if [words[i+j][2] for j in range(len(ws))]==ws: hits.append(words[i:i+len(ws)])
    return hits[occ] if len(hits)>occ else None
def resolve_beats(key, words):
    beats=[]
    for b in SCRIPTS[key]['beats']:
        hit=find_phrase(words,b['a'],b.get('occ',0))
        if not hit: raise SystemExit(f'beat anchor not found in words-{key}.json: {b["a"]!r}')
        b2=dict(b); b2['t0']=hit[0][0]; b2['t1']=hit[-1][1]; b2['wtimes']=[w[0] for w in hit]; beats.append(b2)
    beats.sort(key=lambda b:b['t0'])
    for i,b in enumerate(beats):
        natural_end=b['t1']+b.get('hold',2.4)
        if i+1<len(beats):
            latest_end=beats[i+1]['t0']-0.64; b['end_t']=max(b['t0']+0.35,min(natural_end,latest_end))
        else: b['end_t']=natural_end
    return beats
def resolve_scenes(key, words, total_dur):
    raw_scenes=SCRIPTS[key]['scenes']; resolved=[]
    for idx,sc in enumerate(raw_scenes):
        sc2=dict(sc)
        if idx==0 or not sc.get('a'): sc2['t0']=0.0
        else:
            hit=find_phrase(words,sc['a'],sc.get('occ',0))
            if not hit: raise SystemExit(f'scene anchor not found in words-{key}.json: {sc["a"]!r}')
            sc2['t0']=max(0.0,hit[0][0]-0.15)
        resolved.append(sc2)
    for idx in range(1,len(resolved)):
        if resolved[idx]['t0']<=resolved[idx-1]['t0']:
            raise SystemExit(f"scene order error in {key}: {resolved[idx]['kicker']!r} t0={resolved[idx]['t0']:.2f} <= previous {resolved[idx-1]['t0']:.2f} — list scenes in spoken order")
    for idx in range(len(resolved)): resolved[idx]['t1']=resolved[idx+1]['t0'] if idx+1<len(resolved) else total_dur
    return resolved

# --------------------------------------------------- speech-synced beats ----
def build_music_plan(key, words, beats):
    hushes,swells=[],[]
    for b in beats:
        if b.get('kind')=='count':
            big=b.get('num',0)>=1000 or 'txt' in b
            if big: swells.append(b['t0']+b.get('dur',1.35))
        elif b.get('kind') in ('quote','date'): swells.append(b['t0']+(0.3 if b['kind']=='date' else 0.0))
    for cue in SCRIPTS[key].get('sfx_cues',[]):
        if 'hush' not in cue: continue
        h=dict(cue['hush']); hit=find_phrase(words,h['a'],h.get('occ',0))
        if not hit: raise SystemExit(f"hush anchor not found: {h['a']!r}")
        hushes.append(dict(t=hit[0][0],dur=h.get('dur',1.2),depth=h.get('depth',0.85),lead=h.get('lead',0.5)))
    return hushes,swells

SLOT_MAP={'C':(360,580),'TC':(360,480),'BC':(360,720)}
SLOT_CYCLE=['C','TC','C','BC','C']
def _word_times(b,n):
    if n==len(b['wtimes']): return list(b['wtimes'])
    if n<=1: return [b['t0']]*n
    span=max(0.25,b['t1']-b['t0']); return [b['t0']+span*i/(n-1) for i in range(n)]
def _flash_ring(layer,t,t0,cx,cy):
    dt=t-t0
    if dt<0 or dt>0.48: return
    e=clamp01(dt/0.48); r=36+80*ease_out_expo(e); a=int(145*(1.0-e))
    if a<=2: return
    ring=Image.new('L',(int(r*2)+8,int(r*2)+8),0)
    ImageDraw.Draw(ring).ellipse([0,0,ring.width-1,ring.height-1],fill=a)
    ImageDraw.Draw(ring).ellipse([10,10,ring.width-11,ring.height-11],fill=0)
    ring=ring.filter(ImageFilter.GaussianBlur(2))
    col=Image.new('RGBA',ring.size,YELLOW+(255,)); col.putalpha(ring)
    layer.alpha_composite(col,(int(cx-ring.width/2),int(cy-ring.height/2)))
def _beat_envelope(b,t,pre=0.22,fade_out=0.32):
    t0,end_t=b['t0'],b['end_t']
    if t<t0-pre or t>end_t+fade_out: return 0.0,0.0
    ea=ease_out_expo(clamp01((t-(t0-pre))/0.36)); out_a=1.0 if t<=end_t else 1.0-ease_in_out_sine((t-end_t)/fade_out)
    return ea,out_a

def beat_count(layer,b,t,cx,cy):
    ea,out_a=_beat_envelope(b,t)
    if ea*out_a<=0.01: return
    t0=b['t0']; dur=min(b.get('dur',1.25),max(0.45,b['end_t']-t0)); local=clamp01((t-t0)/dur)
    if 'txt' in b: shown=b['txt']; pop=0.92+0.08*ease_out_back(clamp01((t-(t0-0.1))/0.38))
    else: val=b.get('num',0)*ease_out_expo(local); shown=f"{b.get('pre','')}{val:,.{b.get('dec',0)}f}{b.get('suf','')}"; pop=0.92+0.08*ease_out_back(clamp01((t-(t0-0.1))/0.35))
    fnum=fnt('Black',58 if b.get('big',True) else 48); fnote=fnt('Bold',13)
    d=ImageDraw.Draw(layer); wnum=d.textlength(shown,font=fnum)
    label=b.get('label',''); wlab=tracked_width(d,label,fnote,2.0) if label else 0
    panel_w=int(max(wnum+56,wlab+56,260)); panel_h=130 if label else 98
    px=int(cx-panel_w/2); py=int(cy-panel_h/2 -(1.0-out_a)*18)
    layer.alpha_composite(card_alpha(glass_card(panel_w,panel_h,radius=18),ea*out_a),(px,py))
    d.rectangle([px+20,py+12,px+20+int((panel_w-40)*ease_out_expo(local)),py+16],fill=YELLOW+(int(240*ea*out_a),))
    im=Image.new('RGBA',(int(wnum)+20,82),(0,0,0,0)); ImageDraw.Draw(im).text((10,4),shown,font=fnum,fill=WHITE+(255,))
    if abs(pop-1.0)>0.01:
        nw,nh=max(2,int(im.width*pop)),max(2,int(im.height*pop)); im=im.resize((nw,nh),Image.BICUBIC)
    im.putalpha(im.getchannel('A').point(lambda v:int(v*ea*out_a)))
    layer.alpha_composite(im,(int(cx-im.width/2),int(py+18)))
    if label:
        la=clamp01((t-(t0+0.15))/0.42)*ea*out_a
        if la>0.02: draw_tracked(d,label,fnote,cx-wlab/2,py+panel_h-26,ICE+(int(245*la),),2.0)
    _flash_ring(layer,t,t0+dur*0.85,cx,cy)

def beat_phrase(layer,b,t,cx,cy):
    ea,out_a=_beat_envelope(b,t,pre=0.24)
    if ea*out_a<=0.01: return
    disp=b['words']; ts=_word_times(b,len(disp)); f=fnt('Black',26); tr=5.0; d=ImageDraw.Draw(layer)
    widths=[d.textlength(w,font=f)+tr for w in disp]; total=sum(widths)-tr
    if total>580: f=fnt('Black',20); widths=[d.textlength(w,font=f)+tr for w in disp]; total=sum(widths)-tr
    pw=int(total+48); ph=78; px=int(cx-pw/2); py=int(cy-ph/2 -(1.0-out_a)*18)
    layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),ea*out_a),(px,py))
    x0=cx-total/2.0; x=x0; hi=b.get('hi',-1)
    for i,(w,wt) in enumerate(zip(disp,ts)):
        local=clamp01((t-(wt-0.18))/0.38)
        if local>0:
            e=ease_out_expo(local); a=int(255*min(1.0,local*1.9)*out_a); col=YELLOW if i==hi else WHITE
            yy=py+20+(1.0-e)*18; d.text((x,yy),w,font=f,fill=col+(a,))
        x+=widths[i]
    prog=clamp01((t-(b['t0']-0.08))/max(0.35,b['t1']-b['t0']+0.25))
    if prog>0: uw=total*ease_out_expo(prog); d.rectangle([x0,py+ph-16,x0+uw,py+ph-12],fill=YELLOW+(int(235*ea*out_a),))

def beat_quote(layer,b,t,cx,cy):
    ea,out_a=_beat_envelope(b,t,pre=0.30)
    if ea*out_a<=0.01: return
    disp=b['words']; ts=_word_times(b,len(disp)); fq=fnt('Bold',20 if len(disp)>6 else 24); fmark=fnt('Black',70); fat=fnt('SemiBold',12); d=ImageDraw.Draw(layer)
    mid=(len(disp)+1)//2; lines=[disp[:mid],disp[mid:]]; lts=[ts[:mid],ts[mid:]]
    line_w=[sum(d.textlength(w,font=fq)+7 for w in lw)-7 for lw in lines if lw]
    pw=int(min(W-28,max(line_w)+72)); ph=140 if len(lines)>1 and lines[1] else 100; px=int(cx-pw/2); py=int(cy-ph/2 -(1.0-out_a)*18)
    layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=18),ea*out_a),(px,py))
    ma=int(240*ea*out_a); d.text((px+12,py+6),'\u201c',font=fmark,fill=YELLOW+(ma,))
    for li,(lw,lt) in enumerate(zip(lines,lts)):
        widths=[d.textlength(w,font=fq)+7 for w in lw]; total=sum(widths)-7; x=cx-total/2.0+10; y=py+26+li*32
        for i,(w,wt) in enumerate(zip(lw,lt)):
            local=clamp01((t-(wt-0.18))/0.42)
            if local>0: e=ease_out_expo(local); a=int(255*min(1.0,local*1.9)*out_a); yy=y+(1.0-e)*14; d.text((x,yy),w,font=fq,fill=WHITE+(a,))
            x+=widths[i]
    if b.get('attrib'):
        la=clamp01((t-(b['t0']+0.25))/0.48)*ea*out_a
        if la>0.02:
            aw=tracked_width(d,b['attrib'],fat,1.8); draw_tracked(d,b['attrib'],fat,cx-aw/2,py+ph-22,YELLOW+(int(240*la),),1.8)

def beat_date(layer,b,t,cx,cy):
    ea,out_a=_beat_envelope(b,t,pre=0.24)
    if ea*out_a<=0.01: return
    t0=b['t0']; fm=fnt('Black',32); fs=fnt('Bold',13); d=ImageDraw.Draw(layer)
    wm=tracked_width(d,b['main'],fm,2.2); ws=tracked_width(d,b.get('sub',''),fs,2.4) if b.get('sub') else 0
    pw,ph=int(max(wm,ws)+52),88; px=int(cx-pw/2); py=int(cy-ph/2 -(1.0-out_a)*18)
    layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=14),ea*out_a),(px,py))
    bl=int(14*ea); ba=int(235*ea*out_a)
    for bx,by,dx,dy in ((px+6,py+6,1,1),(px+pw-7,py+6,-1,1),(px+6,py+ph-7,1,-1),(px+pw-7,py+ph-7,-1,-1)):
        x_a,x_b=sorted([bx,bx+bl*dx]); y_a,y_b=sorted([by,by+bl*dy])
        d.rectangle([x_a,by,x_b,by+2],fill=YELLOW+(ba,)); d.rectangle([bx,y_a,bx+2,y_b],fill=YELLOW+(ba,))
    kinetic_line(layer,b['main'],fm,cx,py+14,t,t0-0.18,WHITE,2.2,stagger=0.03,dur=0.42,slide=16,out_a=ea*out_a)
    if b.get('sub'):
        la=clamp01((t-(t0+0.18))/0.42)*ea*out_a
        if la>0.02: draw_tracked(d,b['sub'],fs,cx-ws/2,py+52,ICE+(int(240*la),),2.4)

BEAT_KINDS={'count':beat_count,'phrase':beat_phrase,'quote':beat_quote,'date':beat_date}

def tease_layer(teases, t):
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    for tr in teases:
        t0=tr['t']
        if t<t0 or t>t0+2.9: continue
        ea=ease_out_expo(clamp01((t-t0)/0.5)); out_a=1.0-clamp01((t-(t0+2.25))/0.5); dy=(1-ea)*-28
        ftag=fnt('Black',12); ftxt=fnt('Bold',15); d=ImageDraw.Draw(layer)
        wtag=tracked_width(d,'AHEAD',ftag,2.2); wtxt=tracked_width(d,tr['text'],ftxt,1.4)
        pw=int(wtag+wtxt+52); ph=36; px=W//2-pw//2; py=int(880+dy)
        layer.alpha_composite(card_alpha(glass_card(pw,ph,radius=10),ea*out_a),(px,py))
        a=int(255*out_a)
        d.rounded_rectangle([px+8,py+8,px+18+wtag,py+28],radius=5,fill=YELLOW+(int(235*ea*out_a),))
        d.text((px+12,py+9),'AHEAD',font=ftag,fill=NAVY+(a,))
        d.text((px+26+wtag,py+8),tr['text'],font=ftxt,fill=WHITE+(a,))
    return layer

def beats_layer(beats, t, expire_t):
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    for i,b in enumerate(beats):
        if b['t0']>expire_t: continue
        slot_key=b.get('slot',SLOT_CYCLE[i%len(SLOT_CYCLE)]); cx,cy=SLOT_MAP[slot_key]
        BEAT_KINDS[b['kind']](layer,b,t,cx,cy)
    return layer

# --------------------------------------------------------- ambient layer ----
DUST=[((i*149.3)%W,(i*83.7)%H,0.15+(i%5)*0.04,3+(i%3)*2) for i in range(14)]
def ambient_layer(t):
    layer=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(layer)
    for x0,y0,sp,sz in DUST:
        x=int((x0+t*sp*22)%W); y=int((y0-t*sp*30)%H)
        d.ellipse([x,y,x+sz,y+sz],fill=(175,215,255,28))
    return layer

# ------------------------------------------------------------------ scripts ----
SCRIPTS={
    'short-johnstown': dict(
        title=('THE CANAL THAT BROKE A CITY','CONEMAUGH VALLEY · MAY 31, 1889'),
        end=('FOLLOW','Full documentaries + Shorts weekly'),
        out='short-johnstown.mp4',
        narration='short-johnstown.mp3',
        stock_queries=[
            'South Fork Dam Lake Conemaugh Pennsylvania reservoir archival',
            'historic Pennsylvania fishing hunting club lake 1880s',
            'dam spillway screens fish reservoir water',
            'heavy rain reservoir flood dam overflow',
            'historic dam failure flood valley Pennsylvania',
            'flood water train wreckage river debris',
            'historic flood rubble stone bridge fire aftermath',
            'Red Cross disaster relief volunteers historic Pennsylvania',
            'historic courtroom negligence civil liability trial',
        ],
        scenes=[
            dict(a='', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg', kicker='MAY 31, 1889', sub='14 MILES ABOVE JOHNSTOWN', cam='push_in', focus=(0.5,0.42)),
            dict(a='wealthy pittsburgh', img='south-fork-fishing-and-hunting-club-club-3.jpg', kicker='A FISHING CLUB PLAYGROUND', sub='SOUTH FORK CLUB', cam='push_in', focus=(0.5,0.40)),
            dict(a='they filled the spillway', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg', kicker='THE FATAL MODIFICATIONS', sub='SCREENS · CHOKED SPILLWAY · LOWERED CREST', cam='pan_left', focus=(0.5,0.45), viz='dam_anatomy'),
            dict(a='six to eight inches', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg', kicker='6–8 INCHES IN 24 HOURS', sub='NOWHERE LEFT TO GO', cam='pull_out', focus=(0.5,0.42), viz='rain_rising'),
            dict(a='three ten in the often', img='south-fork-dam-lake-conemaugh-johnstown--4.jpg', kicker='3:10 PM · THE DAM FAILS', sub='20M TONS UNLEASHED', cam='push_in', focus=(0.52,0.45), viz='valley_drop'),
            dict(a='twenty million pounds of water', img='johnstown-train-clean.jpg', kicker='36-FOOT WALL OF WATER', sub='HOMES · TRAINS · 10M LBS DEBRIS', cam='pan_right', focus=(0.52,0.45), viz='wave_scale'),
            dict(a='the wreckage', img='johnstown-flood-1889-ruins-destruction-h-1.jpg', kicker='62 ACRES BURNED 3 DAYS', sub='THE STONE BRIDGE INFERNO', cam='push_in', focus=(0.48,0.45), warm=0.18),
            dict(a='the club', img='south-fork-dam-lake-conemaugh-johnstown--1.jpg', kicker='2,209 LIVES LOST', sub='NEVER HELD RESPONSIBLE', cam='pull_out', focus=(0.5,0.42)),
            dict(a='an act of god', img='south-fork-dam-lake-conemaugh-johnstown--2.jpg', kicker='COURT: "ACT OF GOD"', sub='DAMS FAIL BY DECISIONS', cam='push_in', focus=(0.5,0.42)),
        ],
        teases=[
            dict(t=10.5, text='THE DAM BREAKS AT 3:10 PM'),
            dict(t=24.0, text='A 36-FOOT WALL OF WATER'),
            dict(t=34.0, text='THE VERDICT THAT NEVER CAME'),
        ],
        sfx_cues=[
            dict(hush=dict(a='twenty million pounds of water', lead=0.55, dur=1.2, depth=0.88)),
            dict(hush=dict(a='an act of god', lead=0.45, dur=1.3, depth=0.88)),
        ],
        beats=[
            dict(a='two thousand dollar', kind='count', num=2000, pre='$', label='BOUGHT FOR — PITTSBURGH BARONS', dur=1.2, slot='C'),
            dict(a='two thousand two hundred', kind='count', num=2209, label='PEOPLE KILLED', dur=1.3, big=True, slot='C'),
            dict(a='private fishing', kind='phrase', words=['PRIVATE','FISHING','LAKE'], hi=2, slot='TC'),
            dict(a='spillway', kind='phrase', words=['SPILLWAY','CHOKED'], hi=0, slot='C'),
            dict(a='drain pipes', kind='phrase', words=['SCREENS','ON','DRAIN','PIPES'], hi=0, slot='C'),
            dict(a='six to eight inches', kind='count', txt='6–8 IN', label='OF RAIN IN 24 HOURS', dur=1.0, slot='C'),
            dict(a='three ten in the often', kind='date', main='3:10 PM', sub='SOUTH FORK DAM FAILS', slot='C'),
            dict(a='twenty million pounds of water', kind='count', num=20, suf='M', label='TONS OF WATER UNLEASHED', dur=1.3, slot='C'),
            dict(a='wall fell to six', kind='count', txt='36 FT', label='WALL OF WATER', dur=1.0, slot='C'),
            dict(a='three days', kind='date', main='3 DAYS', sub='FIRES BURNED AT STONE BRIDGE', slot='C'),
            dict(a='five months', kind='date', main='5 MONTHS', sub='CLARA BARTON & RED CROSS', slot='C'),
            dict(a='an act of god', kind='quote', words=['AN','ACT','OF','GOD'], attrib='— COURT RULING · $0 LIABILITY', slot='C'),
            dict(a='fail by decisions', kind='phrase', words=['FAIL','BY','DECISIONS'], hi=2, slot='C'),
        ],
        captions=[
            (0,16,'In 1889, a $2,000 dam killed 2,209 people.'),
            (17,24,'Wealthy Pittsburgh industrialists bought the South Fork Dam'),
            (25,31,'just to keep a private fishing lake.'),
            (32,39,'They filled the spillway to widen the road,'),
            (40,53,'and covered the drain pipes with screens so the game fish could not escape.'),
            (54,65,'Then 6 to 8 inches of rain fell in 24 hours.'),
            (66,77,'And at 3:10 in the afternoon, the dam gave way.'),
            (78,89,'20 million tons of water dropped 14 miles in under an hour —'),
            (90,95,'a wall 36 feet high.'),
            (96,101,'The wreckage burned for 3 days.'),
            (102,108,'Clara Barton stayed 5 months.'),
            (109,114,'And the club? Never held responsible.'),
            (115,123,'For the courts called it an act of God.'),
            (124,130,'But dams do not fail by accident.'),
            (131,134,'They fail by decisions.'),
        ],
    ),
    'short-enron': dict(
        title=('HOW ENRON DIED','HOUSTON, TEXAS · DEC 2, 2001'),
        end=('FOLLOW','Money, Explained — new every week'),
        out='short-enron.mp4',
        narration='short-enron.mp3',
        stock_queries=[
            'Houston energy company corporate headquarters skyline 2001',
            'stock market trading floor rising share prices ticker',
            'corporate innovation technology office skyscraper',
            'financial journalist newspaper investigation corporate accounting',
            'corporate fraud CFO executive courtroom trial',
            'energy trading control room accounting ledger',
            'shell company financial paperwork accounting records',
            'corporate bankruptcy newspaper headline stock market crash',
            'office employees corporate layoffs retirement pension',
            'corporate executives fraud trial courtroom justice',
        ],
        scenes=[
            dict(a='', img='enron-corporation-headquarters-houston-c-4.jpg', kicker='WINTER 2001 · HOUSTON', sub='MOST INNOVATIVE COMPANY UNRAVELS', cam='tilt_up', focus=(0.5,0.40)),
            dict(a='ninety dollars', img='enron-bankruptcy-newspaper-headline-2001-3.jpg', kicker='PEAK: $90.75 / SHARE', sub='NYSE: ENE · AUG 2000', cam='push_in', focus=(0.5,0.42), viz='stock_boom'),
            dict(a='fortune my busy nostra', img='enron-corporation-headquarters-houston-c-4.jpg', kicker='FORTUNE · 6 YEARS RUNNING', sub='"MOST INNOVATIVE COMPANY"', cam='pull_out', focus=(0.5,0.42)),
            dict(a='is enron overpriced', img='enron-corporation-headquarters-houston-c-3.jpg', kicker='MAR 2001 · BETHANY McLEAN', sub='"IS ENRON OVERPRICED?"', cam='pan_right', focus=(0.5,0.42)),
            dict(a='the profits were fiction', img='andrew-fastow-enron-cfo-trial-photo-2.jpg', kicker='CFO ANDREW FASTOW', sub='ARCHITECT OF THE ILLUSION', cam='push_in', focus=(0.48,0.40)),
            dict(a='mom to market accounting', img='enron-corporation-headquarters-houston-c-5.jpg', kicker='MARK-TO-MARKET', sub='10 YRS PROFIT BOOKED DAY ONE', cam='pan_left', focus=(0.48,0.42), viz='mtm_ledger'),
            dict(a='off the books', img='enron-bankruptcy-newspaper-headline-2001-1.jpg', kicker='LJM · RAPTOR · CHEWCO', sub='$30B+ DEBT IN SHELL ENTITIES', cam='push_in', focus=(0.5,0.42), viz='shell_maze'),
            dict(a='december second', img='enron-corporation-headquarters-houston-c-2.jpg', kicker='DEC 2, 2001 · CHAPTER 11', sub='$63.4B — LARGEST US BANKRUPTCY', cam='pull_out', focus=(0.5,0.42), viz='stock_crash'),
            dict(a='twenty thousand employees', img='enron-corporation-headquarters-houston-c-1.jpg', kicker='20,000 JOBS & PENSIONS GONE', sub='85,000 AT ANDERSEN DISSOLVED', cam='pan_right', focus=(0.52,0.42)),
            dict(a='they called themselves', img='jeff-skilling-ken-lay-enron-trial-courtr-2.jpg', kicker='THE RECKONING', sub='FASTOW & SKILLING IMPRISONED', cam='push_in', focus=(0.48,0.40)),
        ],
        teases=[
            dict(t=9.5, text='ONE QUESTION ENDS IT ALL'),
            dict(t=19.0, text='THE BOOKS WERE FAKE'),
            dict(t=30.0, text='DEC 2 — CHAPTER 11'),
        ],
        sfx_cues=[
            dict(hush=dict(a='is enron overpriced', lead=0.50, dur=1.2, depth=0.88)),
            dict(hush=dict(a='december second', lead=0.55, dur=1.3, depth=0.90)),
            dict(hush=dict(a='the company cannot', lead=0.50, dur=1.4, depth=0.85)),
        ],
        beats=[
            dict(a='six years in a row', kind='phrase', words=['6','YEARS','IN','A','ROW'], hi=0, slot='C'),
            dict(a='ninety dollars', kind='count', num=90.75, dec=2, pre='$', label='PEAK SHARE PRICE', dur=1.0, slot='C'),
            dict(a='seventy billion dollars', kind='count', num=70, pre='$', suf='B', label='PEAK VALUATION', dur=1.2, slot='C'),
            dict(a='is enron overpriced', kind='quote', hold=3.0, words=['IS','ENRON','OVERPRICED?'], attrib='— BETHANY McLEAN, FORTUNE', slot='C'),
            dict(a='the profits were fiction', kind='phrase', words=['PROFITS','WERE','FICTION'], hi=2, slot='C'),
            dict(a='mom to market accounting', kind='phrase', words=['MARK-TO-MARKET'], hi=0, size=26, slot='C'),
            dict(a='off the books partnerships', kind='phrase', words=['OFF-BOOKS','PARTNERSHIPS'], hi=0, slot='C'),
            dict(a='december second', kind='date', main='DEC 2, 2001', sub='CHAPTER 11 FILED', slot='C'),
            dict(a='sixty three billion dollars', kind='count', num=63.4, pre='$', suf='B', dec=1, label='IN ASSETS WIPED OUT', dur=1.3, slot='C'),
            dict(a='twenty thousand employees', kind='count', num=20000, label='JOBS & PENSIONS GONE', dur=1.2, slot='C'),
            dict(a='eighty five thousand', kind='count', num=85000, label='AT ANDERSEN DISSOLVED', dur=1.2, slot='C'),
            dict(a='the smartest guys in the room', kind='quote', words=['SMARTEST','GUYS','IN','THE','ROOM'], attrib='— ENRON SLOGAN', slot='C'),
            dict(a='it is not making money', kind='quote', words=['IF','IT','CANNOT','EXPLAIN','IT,','IT\'S','NOT','MAKING','MONEY.'], attrib='— THE LESSON', slot='C'),
        ],
        captions=[
            (0,11,"Enron was voted America's most innovative company, 6 years in a row."),
            (12,15,'Its stock hit $90.'),
            (16,22,'The market value passed $70 billion.'),
            (23,29,'Then Fortune magazine asked one question:'),
            (30,32,'Is Enron overpriced?'),
            (33,36,'The profits were fiction'),
            (37,47,'— projected decades of earnings, booked the day the deal was signed.'),
            (48,51,'Mark-to-market accounting,'),
            (52,57,'hidden in off-the-books partnerships,'),
            (58,63,'run by the chief financial officer.'),
            (64,73,'On Dec 2, 2001, Enron filed for bankruptcy.'),
            (74,79,'$63 billion in assets.'),
            (80,88,'20,000 employees lost their jobs & pensions.'),
            (89,96,'Arthur Andersen — 85,000 people —'),
            (97,99,'dissolved overnight.'),
            (100,108,'They called themselves the smartest guys in the room.'),
            (109,117,'If a company cannot explain how it makes money,'),
            (118,122,'it is not making money.'),
            (123,127,'Follow for Money, Explained.'),
        ],
    ),
}

# -------------------------------------------------------------------- main ----
def main(key):
    cfg=SCRIPTS[key]
    out=os.path.join(ROOT,'social',cfg['out'])
    nar_src=os.path.join(AUDIO,cfg['narration'])
    nar=os.path.join(AUDIO,f'narration-{key}.m4a')
    # Single-file narration: transcode to AAC m4a for precise mux
    shutil.copy(nar_src, '/tmp/_short_in.mp3')
    cmd=[FFMPEG,'-y','-i','/tmp/_short_in.mp3','-c:a','aac','-b:a','160k',nar]
    subprocess.run(cmd,check=True,capture_output=True)
    adur=duration(nar); total=adur+1.6; n=int(total*FPS)
    words=load_words(key); beats=resolve_beats(key,words); scenes=resolve_scenes(key,words,total)
    cap_stream=build_caption_stream(key,words)
    # Free stock acquisition is clip-first across Pexels, Pixabay, Openverse,
    # Wikimedia Commons and NASA; existing story photos remain the guaranteed
    # offline fallback. API keys are optional free-tier GitHub secrets.
    if os.environ.get('ENABLE_STOCK_BROLL','1').strip().lower() not in ('0','false','no','off'):
        try:
            from pipeline.assets import fetch_scene_assets
            stock_dir=os.path.join(ROOT,'output','short-stock',key)
            for si,sc in enumerate(scenes):
                queries=cfg.get('stock_queries',[])
                query=queries[si] if si<len(queries) else sc.get('kicker','documentary b-roll')
                sc['stock_query']=query
                found=fetch_scene_assets(query,si,stock_dir,count=1,target_width=W,target_height=H,allow_generated=False)
                if found:
                    asset=found[0]; sc['media_path']=str(asset.path); sc['media_kind']=asset.kind
                    sc['source']=asset.source; sc['source_url']=asset.origin_url; sc['license_note']=asset.license_note
                    sc['source_size']=(asset.width,asset.height)
        except Exception as exc:
            print(f'  stock sourcing unavailable; using authored story stills: {exc!r}')
    print(f'[{key}] narration={adur:.1f}s total={total:.1f}s ({n}f) scenes={len(scenes)} beats={len(beats)}')
    cuts=[sc['t0'] for sc in scenes]
    hushes,swells=build_music_plan(key,words,beats)
    generate_score(key,total,cuts,[],[],hushes,swell_hits=swells)
    plate_cache={}
    for sc in scenes:
        source_path=sc.get('media_path') or os.path.join(IMG,sc['img'])
        pkey=(source_path,sc.get('warm',0.0))
        if sc.get('media_kind')=='video':
            # Video frames are decoded live; keep a real story photograph as a
            # failure-safe. Even a broken URL/codec cannot blank a scene.
            fallback=os.path.join(IMG,sc['img'])
            if not os.path.exists(fallback): raise SystemExit(f'missing fallback image {fallback}')
            if fallback not in plate_cache: plate_cache[fallback]=prep_plate(fallback,sc.get('warm',0.0))
            sc['fallback_plate']=plate_cache[fallback]; sc['plate']=None
            print(f"  scene {sc['t0']:5.1f}-{sc['t1']:5.1f}s | VIDEO {sc.get('source')} {sc.get('source_size')} | {os.path.basename(source_path)}")
        else:
            if not os.path.exists(source_path): raise SystemExit(f'missing image {source_path}')
            if pkey not in plate_cache: plate_cache[pkey]=prep_plate(source_path,sc.get('warm',0.0))
            sc['plate']=plate_cache[pkey]
            label=(f"{sc.get('source')} {sc.get('source_size')}" if sc.get('media_path') else sc['img'])
            print(f"  scene {sc['t0']:5.1f}-{sc['t1']:5.1f}s | PHOTO {label}")
    # Surface licence problems while the operator is still watching, not only in the JSON.
    for _line in LICENCE_REPORT(sorted({sc['img'] for sc in scenes if not sc.get('media_path')})):
        print(_line)

    music=os.path.join(AUDIO,f'music-{key}.wav')
    proc=subprocess.Popen([FFMPEG,'-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',nar,'-i',music,
        '-filter_complex','[2:a]volume=0.60[m];[1:a]aformat=channel_layouts=stereo,volume=1.0[v];[m][v]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]',
        '-map','0:v','-map','[a]','-c:v','libx264','-preset','fast','-crf','22','-maxrate','1600k','-bufsize','3200k','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',out],
        stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    FADE=0.42; nscenes=len(scenes); expire_t=adur-0.5
    active_video_scene=-1; video_proc=None
    for i in range(n):
        t=i/FPS
        k=0
        for idx,sc in enumerate(scenes):
            if t>=sc['t0']: k=idx
            else: break
        sc=scenes[k]; sc_dur=max(0.5,sc['t1']-sc['t0']); pos=t-sc['t0']; p=clamp01(pos/sc_dur)
        if sc.get('media_kind')=='video':
            if active_video_scene!=k:
                stop_video_plate(video_proc)
                try: video_proc=video_plate_reader(sc['media_path']); active_video_scene=k
                except Exception as exc: video_proc=None; active_video_scene=-1; print(f'  video decode fallback: {exc!r}')
            source=read_video_plate(video_proc) if video_proc else None
            if source is None:
                source=sc['fallback_plate']; sc['media_kind']='image'; sc['used_fallback']=True
                stop_video_plate(video_proc)
                video_proc=None; active_video_scene=-1
        else:
            stop_video_plate(video_proc)
            video_proc=None; active_video_scene=-1; source=sc['plate']
        sc['last_source']=source
        extra_z=1.0+0.012*(1.0-ease_out_cubic(clamp01(pos/FADE))) if (k>0 and pos<FADE) else 1.0
        frame=camera_frame(source,p,sc.get('cam','push_in'),sc.get('focus',(0.5,0.42)),extra_zoom=extra_z)
        if k>0 and pos<FADE:
            prev=scenes[k-1]; u=pos/FADE; prev_z=1.0+0.008*ease_in_out_sine(u)
            prev_plate=prev.get('last_source',prev.get('plate'))
            f_prev=camera_frame(prev_plate,1.0,prev.get('cam','push_in'),prev.get('focus',(0.5,0.42)),extra_zoom=prev_z)
            frame=optical_flare_transition(f_prev,frame,u)
        ov=Image.new('RGBA',(W,H),(0,0,0,0))
        ov.alpha_composite(ambient_layer(t))
        ov.alpha_composite(viz_layer(sc.get('viz'),pos,sc_dur))
        ov.alpha_composite(beats_layer(beats,t,expire_t))
        ov.alpha_composite(tease_layer(cfg.get('teases',[]),t))
        if t<4.0: cold_open_overlay(ov,cfg['title'],t,dur=4.0)
        ov.alpha_composite(hud_chapter_layer(sc['kicker'],sc.get('sub',''),k+1,nscenes,pos,sc_dur,t/total))
        ov.alpha_composite(caption_ribbon_layer(cap_stream,t))
        frame=Image.alpha_composite(frame.convert('RGBA'),ov).convert('RGB')
        if t>=adur-0.4: frame=end_card_overlay(frame,cfg['end'],t-(adur-0.4),total-(adur-0.4))
        proc.stdin.write(frame.tobytes())
        if i%360==0: print(f'  frame {i}/{n}',flush=True)
    stop_video_plate(video_proc)
    proc.stdin.close()
    if proc.wait()!=0: raise SystemExit('encode failed')
    report=[]
    for si,sc in enumerate(scenes):
        report.append(dict(scene=si+1,query=(cfg.get('stock_queries') or ['']*len(scenes))[si],
            media=('authored photo fallback' if not sc.get('media_path') or sc.get('used_fallback') else sc.get('media_kind')),
            provider=sc.get('source','existing story archive'),source_url=sc.get('source_url',''),
            # Authored stills report their real ledger status instead of one blanket
            # "metadata unavailable" string — see image-search/LICENSES.yml.
            license=(sc.get('license_note') if sc.get('media_path') else LICENCE_NOTE(sc.get('img',''))),
            dimensions=sc.get('source_size',None),fallback=(not bool(sc.get('media_path')) or bool(sc.get('used_fallback',False))),file=sc.get('media_path',sc.get('img',''))))
    report_dir=os.path.join(ROOT,'output','short-stock',key); os.makedirs(report_dir,exist_ok=True)
    with open(os.path.join(report_dir,'scene-sources.json'),'w',encoding='utf-8') as f: json.dump(report,f,indent=2,ensure_ascii=False)
    print('source log',os.path.join(report_dir,'scene-sources.json'))
    print('done',out,os.path.getsize(out)//1024,'KB')

if __name__=='__main__':
    arg=sys.argv[1] if len(sys.argv)>1 else 'short-johnstown'
    if arg not in SCRIPTS: raise SystemExit(f'unknown script {arg!r} — choose from {sorted(SCRIPTS)}')
    main(arg)
