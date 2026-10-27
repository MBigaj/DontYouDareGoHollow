#!/usr/bin/env python3
"""
ASHEN pixel pipeline - turns full-resolution art into consistent, game-ready pixel art.

Steps: load -> background removal -> crop to subject -> fit to preset size ->
crisp downscale (contrast-weighted majority vote, or area average + dither) ->
snap to the shared palette (perceptual Lab matching) -> limit colour count ->
orphan-pixel cleanup -> 1px selective outline -> export native, preview, before/after.

Usage:
  python pixelate.py art/knight.png --preset character
  python pixelate.py art/*.png --preset character --sheet
  python pixelate.py bg.jpg --preset landscape
  python pixelate.py boss.png --preset boss --height 200 --outline dark
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from scipy.ndimage import label, binary_dilation, binary_erosion

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ presets
PRESETS = {
    #            fit box (w,h)  mode        colours dither outline     bg      pad
    "character": dict(size=(None, 96),  mode="kcentroid", colors=16, dither=0.0, outline="selective", bg="auto", pad=2),
    "boss":      dict(size=(None, 192), mode="kcentroid", colors=24, dither=0.0, outline="selective", bg="auto", pad=2),
    "item":      dict(size=(32, 32),    mode="kcentroid", colors=16, dither=0.0, outline="selective", bg="auto", pad=1),
    "equipment": dict(size=(64, 64),    mode="kcentroid", colors=18, dither=0.0, outline="selective", bg="auto", pad=2),
    "portrait":  dict(size=(64, 64),    mode="kcentroid", colors=18, dither=0.0, outline="none",      bg="keep", pad=0),
    "landscape": dict(size=(480, None), mode="kcentroid", colors=48, dither=0.0, outline="none",     bg="keep", pad=0, harmonize=0.15),
}

BAYER = np.array([[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]], float) / 16.0

# ------------------------------------------------------------------ colour
def read_hex(spec):
    path = spec if os.path.exists(spec) else os.path.join(HERE, "palettes", spec + ".hex")
    cols = []
    for line in open(path):
        line = line.split(";")[0].strip()
        if line:
            cols.append([int(line[i:i + 2], 16) for i in (0, 2, 4)])
    return np.array(cols, np.uint8)

def kmeans_palette(rgb_pixels, n, seed=0, iters=20):
    """k-means in Lab on the subject's pixels; returns n RGB colours."""
    rng = np.random.default_rng(seed)
    px = rgb_pixels.reshape(-1, 3)
    if len(px) > 60000: px = px[rng.choice(len(px), 60000, replace=False)]
    lab = to_lab(px)
    C = [lab[rng.integers(len(lab))]]
    d = ((lab - C[0]) ** 2).sum(1)
    for _ in range(n - 1):                         # farthest-point init keeps small accents (glows, eyes)
        C.append(lab[d.argmax()]); d = np.minimum(d, ((lab - C[-1]) ** 2).sum(1))
    C = np.array(C)
    for _ in range(iters):
        a = nearest(lab[:, None, :], C)[:, 0]
        for k in range(n):
            m = a == k
            if m.any(): C[k] = lab[m].mean(0)
    a = nearest(lab[:, None, :], C)[:, 0]
    out = np.array([px[a == k].mean(0) if (a == k).any() else px[0] for k in range(n)])
    return out.clip(0, 255).astype(np.uint8)

def load_palette(spec, rgb_pixels, n=32, harmonize=0.35):
    """'ashen'  : strict shared master palette (maximum consistency)
       'auto'   : colours extracted from the art (maximum fidelity)
       'harmonized' (default): extracted colours pulled toward the master palette"""
    if spec in ("auto", "harmonized"):
        pal = kmeans_palette(rgb_pixels, n)
        if spec == "harmonized":
            master = read_hex("ashen")
            j = nearest(to_lab(pal)[None], to_lab(master))[0]
            pal = (pal * (1 - harmonize) + master[j] * harmonize).round().astype(np.uint8)
        return np.unique(pal, axis=0)
    return read_hex(spec)

def to_lab(rgb):
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)

def from_lab(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116; fx = fy + a / 500; fz = fy - b / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    Mi = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    c = np.clip(xyz @ Mi.T, 0, 1)
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
    return (c * 255).round().clip(0, 255).astype(np.uint8)

def prepare_values(rgb, mask, lo_hi=(6, 90), gamma=0.8, chroma=1.25, sharpen=1.0, block=6, smooth=1.0):
    """Pixel art needs readable value steps. Stretch the subject's lightness range, lift mid-tones,
    boost colour, and sharpen at the scale that will survive the downscale."""
    if smooth:   # edge-preserving smoothing: removes painterly grime that would become pixel noise
        import cv2
        d = int(max(5, block * 0.9)) | 1
        rgb = cv2.bilateralFilter(np.ascontiguousarray(rgb), d, 28 * smooth, block * 0.8)
        rgb = cv2.edgePreservingFilter(rgb, flags=1, sigma_s=max(10, block * 4), sigma_r=0.25 * smooth)
    lab = to_lab(rgb)
    Ls = lab[..., 0][mask]
    p_lo, p_hi = np.percentile(Ls, 1.5), np.percentile(Ls, 99.7)
    t = np.clip((lab[..., 0] - p_lo) / max(p_hi - p_lo, 1), 0, 1) ** gamma
    lab[..., 0] = lo_hi[0] + t * (lo_hi[1] - lo_hi[0])
    lab[..., 1:] *= chroma
    out = Image.fromarray(from_lab(lab))
    if sharpen:
        out = out.filter(ImageFilter.UnsharpMask(radius=max(1, block * 0.6), percent=int(140 * sharpen), threshold=2))
    return np.array(out)

def nearest(lab, pal_lab, chunk=200000):
    flat = lab.reshape(-1, 3); out = np.empty(len(flat), int)
    for i in range(0, len(flat), chunk):
        d = ((flat[i:i + chunk, None, :] - pal_lab[None]) ** 2).sum(-1)
        out[i:i + chunk] = d.argmin(1)
    return out.reshape(lab.shape[:-1])

# ------------------------------------------------------------------ background
def remove_background(rgba, mode="auto", tol=18.0, min_part=0.004, holes=True):
    a = rgba[..., 3] > 127
    if mode == "ai":                             # subject segmentation for busy/scenic backgrounds
        from rembg import remove, new_session
        cut = np.array(remove(Image.fromarray(rgba), session=new_session("isnet-general-use")))
        fg = cut[..., 3] > 140
        lbl, n = label(fg)
        if n > 1:
            sizes = np.bincount(lbl.ravel()); sizes[0] = 0
            fg = sizes[lbl] >= min_part * sizes.max()
        return binary_erosion(fg, iterations=1)
    if mode == "keep":
        return np.ones(a.shape, bool)
    if (~a).sum() > 0.02 * a.size:              # already has transparency
        return a
    lab = to_lab(rgba[..., :3])
    H, W = a.shape; b = max(2, min(H, W) // 100)
    if mode == "auto":                           # up to 3 dominant colours in the border band (handles gradients)
        band = np.concatenate([lab[b:2*b].reshape(-1, 3), lab[-2*b:-b].reshape(-1, 3),
                               lab[:, b:2*b].reshape(-1, 3), lab[:, -2*b:-b].reshape(-1, 3)])
        rng = np.random.default_rng(0); C = band[rng.choice(len(band), 3)]
        for _ in range(10):
            asg = nearest(band[:, None], C)[:, 0]
            C = np.array([band[asg == k].mean(0) if (asg == k).any() else C[k] for k in range(3)])
        cnt = np.bincount(nearest(band[:, None], C)[:, 0], minlength=3)
        bgs = C[cnt > 0.08 * len(band)]
    else:
        bgs = to_lab(np.array([[int(mode.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]]))
    dist = np.min([np.sqrt(((lab - c) ** 2).sum(-1)) for c in bgs], axis=0)
    near = dist < tol
    near[:b] = near[-b:] = True; near[:, :b] = near[:, -b:] = True   # frame / border lines count as background
    lbl, n = label(near)
    edge_ids = np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))
    fg = ~np.isin(lbl, edge_ids[edge_ids > 0])
    if holes:   # enclosed gaps (between legs, inside a cape) that match the background closely
        tight = dist < tol * 0.6
        hl, hn = label(tight & fg)
        if hn:
            hs = np.bincount(hl.ravel()); hs[0] = 0
            fg &= ~(hs[hl] >= 0.0008 * fg.sum())
    fg = binary_erosion(fg, iterations=1)
    lbl, n = label(fg)                            # drop specks / watermarks far smaller than the subject
    if n > 1:
        sizes = np.bincount(lbl.ravel()); sizes[0] = 0
        fg = sizes[lbl] >= min_part * sizes.max()
    return fg

# ------------------------------------------------------------------ downscale
def fit_size(w, h, box):
    bw, bh = box
    if bw and bh: s = min(bw / w, bh / h)
    elif bw: s = bw / w
    else: s = bh / h
    return max(1, round(w * s)), max(1, round(h * s))

def downscale_majority(rgb, alpha, out_w, out_h, pal, pal_lab, contrast=0.045, bs=6):
    """Each output pixel = the palette colour that wins a vote inside its source block.
    Votes are weighted by local contrast so thin lines, eyes and highlights survive."""
    big = Image.fromarray(rgb).resize((out_w * bs, out_h * bs), Image.LANCZOS)
    big_a = np.array(Image.fromarray(alpha.astype(np.uint8) * 255).resize((out_w * bs, out_h * bs), Image.BOX)) > 127
    lab = to_lab(np.array(big))
    idx = nearest(lab, pal_lab)
    L = lab[..., 0]
    blocksL = L.reshape(out_h, bs, out_w, bs)
    meanL = blocksL.mean(axis=(1, 3), keepdims=True)
    wgt = (1 + contrast * np.abs(blocksL - meanL)).reshape(L.shape)
    wgt = wgt * big_a
    bid = (np.arange(out_h)[:, None, None, None] * out_w + np.arange(out_w)[None, None, :, None])
    bid = np.broadcast_to(bid, (out_h, bs, out_w, bs)).reshape(L.shape)
    votes = np.zeros((out_h * out_w, len(pal)))
    np.add.at(votes, (bid.ravel(), idx.ravel()), wgt.ravel())
    out_idx = votes.argmax(1).reshape(out_h, out_w)
    cover = big_a.reshape(out_h, bs, out_w, bs).mean(axis=(1, 3))
    out_idx[cover < 0.5] = -1
    return out_idx

def downscale_kcentroid(rgb, alpha, out_w, out_h, pal, pal_lab, contrast=0.02, bs=6, k=3, iters=6):
    """Each output pixel = the dominant colour cluster of its source block (k-means per block).
    Keeps edges crisp instead of averaging them into mud; contrast weighting protects thin lines/highlights."""
    big = np.array(Image.fromarray(rgb).resize((out_w * bs, out_h * bs), Image.LANCZOS))
    big_a = np.array(Image.fromarray(alpha.astype(np.uint8) * 255).resize((out_w * bs, out_h * bs), Image.BOX)) > 127
    lab = to_lab(big)
    X = lab.reshape(out_h, bs, out_w, bs, 3).transpose(0, 2, 1, 3, 4).reshape(-1, bs * bs, 3)
    A = big_a.reshape(out_h, bs, out_w, bs).transpose(0, 2, 1, 3).reshape(-1, bs * bs).astype(float)
    L = X[..., 0]
    meanL = (L * A).sum(1, keepdims=True) / np.maximum(A.sum(1, keepdims=True), 1)
    Wt = A * (1 + contrast * np.abs(L - meanL))
    order = np.argsort(L + (1 - A) * 1e3, axis=1)              # init: darkest, median, brightest opaque pixel
    nvalid = np.maximum(A.sum(1).astype(int), 1)
    picks = np.stack([order[np.arange(len(X)), np.minimum((nvalid - 1) * q // (k - 1), bs * bs - 1)] for q in range(k)], 1)
    C = X[np.arange(len(X))[:, None], picks]
    for _ in range(iters):
        d = ((X[:, :, None, :] - C[:, None, :, :]) ** 2).sum(-1)
        asg = d.argmin(-1)
        oh = (asg[..., None] == np.arange(k)) * Wt[..., None]
        tot = oh.sum(1)
        C = np.where(tot[..., None] > 0, (oh[..., None] * X[:, :, None, :]).sum(1) / np.maximum(tot[..., None], 1e-9), C)
    win = C[np.arange(len(X)), tot.argmax(1)]
    out_idx = nearest(win[:, None, :], pal_lab)[:, 0].reshape(out_h, out_w)
    cover = A.mean(1).reshape(out_h, out_w)
    out_idx[cover < 0.5] = -1
    return out_idx

def downscale_average(rgb, alpha, out_w, out_h, pal, pal_lab, dither=0.35):
    small = np.array(Image.fromarray(rgb).resize((out_w, out_h), Image.LANCZOS))
    lab = to_lab(small)
    if dither:
        Y, X = np.mgrid[0:out_h, 0:out_w]
        lab[..., 0] += (BAYER[Y % 4, X % 4] - 0.5) * 9 * dither
    out_idx = nearest(lab, pal_lab)
    a = np.array(Image.fromarray(alpha.astype(np.uint8) * 255).resize((out_w, out_h), Image.BOX)) > 127
    out_idx[~a] = -1
    return out_idx

# ------------------------------------------------------------------ cleanup
def limit_colors(idx, pal_lab, n):
    used = idx[idx >= 0]
    if n <= 0 or len(np.unique(used)) <= n:
        return idx
    keep = np.argsort(np.bincount(used, minlength=len(pal_lab)))[::-1][:n]
    remap = keep[nearest(pal_lab[None, :, :], pal_lab[keep])[0]]
    out = idx.copy(); m = idx >= 0
    out[m] = remap[idx[m]]
    return out

def remove_orphans(idx, P, passes=1):
    """A pixel with no matching 8-neighbour is replaced by its most common neighbour."""
    for _ in range(passes):
        H, W = idx.shape
        pad = np.pad(idx, 1, constant_values=-1)
        neigh = np.stack([pad[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx]
                          for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
        same = (neigh == idx[None]).sum(0)
        counts = np.zeros((H, W, P + 1), int)
        for k in range(8):
            np.add.at(counts, (np.arange(H)[:, None], np.arange(W)[None, :], neigh[k] + 1), 1)
        counts[..., 0] = 0                              # never fill with transparency
        mode = counts.argmax(-1) - 1
        orphan = (same == 0) & (idx >= 0) & (mode >= 0)
        idx = np.where(orphan, mode, idx)
    # drop isolated single opaque pixels (no 4-neighbour)
    a = idx >= 0
    p = np.pad(a, 1)
    n4 = p[:-2, 1:-1].astype(int) + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
    idx = np.where(a & (n4 == 0), -1, idx)
    return idx

def render(idx, pal, pal_lab, outline="selective", pad=2):
    if pad:
        idx = np.pad(idx, pad, constant_values=-1)
    H, W = idx.shape
    rgba = np.zeros((H, W, 4), np.uint8)
    m = idx >= 0
    rgba[m, :3] = pal[idx[m]]; rgba[m, 3] = 255
    if outline != "none":
        ring = binary_dilation(m) & ~m
        if outline == "dark":
            rgba[ring] = (*pal[pal_lab[:, 0].argmin()], 255)
        else:  # selective: a much darker version of the neighbouring colour, snapped to palette
            nb = np.full((H, W), -1)
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                sh = np.roll(idx, (dy, dx), (0, 1))
                nb = np.where((nb < 0) & (sh >= 0), sh, nb)
            dark_lab = pal_lab.copy(); dark_lab[:, 0] *= 0.32; dark_lab[:, 1:] *= 0.55
            dmap = nearest(dark_lab[None], pal_lab)[0]
            rgba[ring, :3] = pal[dmap[nb[ring]]]; rgba[ring, 3] = 255
    return Image.fromarray(rgba, "RGBA")

# ------------------------------------------------------------------ main
def process(path, cfg, pal_spec, outdir, preview):
    src = Image.open(path).convert("RGBA")
    if max(src.size) > 2400:                       # keep it fast
        src.thumbnail((2400, 2400), Image.LANCZOS)
    if cfg.get("enhance", 1.0) != 1.0:
        rgb_im = ImageEnhance.Contrast(src.convert("RGB")).enhance(cfg["enhance"])
        src = Image.merge("RGBA", (*rgb_im.split(), src.split()[3]))
    rgba = np.array(src)
    fg = remove_background(rgba, cfg["bg"], cfg["tol"], cfg["min_part"], cfg["holes"])
    ys, xs = np.where(fg)
    if len(ys) == 0: raise SystemExit(f"{path}: nothing left after background removal; try --bg keep or a lower --tol")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb, alpha = rgba[y0:y1, x0:x1, :3], fg[y0:y1, x0:x1]
    box = cfg["size"]; pad = cfg["pad"]
    inner = (box[0] - 2 * pad if box[0] else None, box[1] - 2 * pad if box[1] else None)
    ow, oh = fit_size(x1 - x0, y1 - y0, inner)
    bs = int(np.clip(min((x1 - x0) / ow, (y1 - y0) / oh), 2, 8))
    if cfg["levels"]:
        rgb = prepare_values(rgb, alpha, gamma=cfg["gamma"], chroma=cfg["chroma"], sharpen=cfg["sharpen"],
                             block=(x1 - x0) / ow, smooth=cfg["smooth"])
    pal = load_palette(pal_spec, rgb[alpha].reshape(-1, 1, 3), cfg["colors"], cfg["harmonize"])
    pal_lab = to_lab(pal)
    if cfg["mode"] == "kcentroid":
        idx = downscale_kcentroid(rgb, alpha, ow, oh, pal, pal_lab, cfg["contrast"], bs)
    elif cfg["mode"] == "majority":
        idx = downscale_majority(rgb, alpha, ow, oh, pal, pal_lab, cfg["contrast"], bs)
    else:
        idx = downscale_average(rgb, alpha, ow, oh, pal, pal_lab, cfg["dither"])
    idx = limit_colors(idx, pal_lab, cfg["colors"])
    if cfg["clean"]:
        idx = remove_orphans(idx, len(pal), passes=cfg['clean_passes'])
    out = render(idx, pal, pal_lab, cfg["outline"], pad)
    if box[0] and box[1]:                          # centre on exact canvas for icons
        canvas = Image.new("RGBA", box, (0, 0, 0, 0))
        canvas.alpha_composite(out, ((box[0] - out.width) // 2, box[1] - out.height if cfg["anchor"] == "bottom" else (box[1] - out.height) // 2))
        out = canvas
    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(outdir, exist_ok=True)
    out.save(f"{outdir}/{name}_px.png")
    big = out.resize((out.width * preview, out.height * preview), Image.NEAREST)
    big.save(f"{outdir}/{name}_px_x{preview}.png")
    # before / after
    ref = src.crop((x0, y0, x1, y1)); ref.thumbnail((10000, big.height), Image.LANCZOS)
    cmp_ = Image.new("RGBA", (ref.width + big.width + 30, big.height + 20), (24, 22, 28, 255))
    cmp_.alpha_composite(ref.convert("RGBA"), (10, 10)); cmp_.alpha_composite(big, (ref.width + 20, 10))
    cmp_.save(f"{outdir}/{name}_compare.png")
    return name, out

def make_sheet(items, outdir, scale=4):
    pad = 12; h = max(o.height for _, o in items) * scale
    W = sum(o.width * scale + pad for _, o in items) + pad
    sheet = Image.new("RGBA", (W, h + 2 * pad + 16), (20, 18, 24, 255))
    d = ImageDraw.Draw(sheet); x = pad
    for name, o in items:
        sheet.alpha_composite(o.resize((o.width * scale, o.height * scale), Image.NEAREST), (x, pad + h - o.height * scale))
        d.text((x, h + pad + 2), name, fill=(200, 190, 170))
        x += o.width * scale + pad
    sheet.save(f"{outdir}/sheet.png")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--preset", default="character", choices=PRESETS)
    ap.add_argument("--width", type=int); ap.add_argument("--height", type=int)
    ap.add_argument("--palette", default="harmonized", help="'harmonized' (default), 'ashen' (strict shared), 'auto', or a .hex file")
    ap.add_argument("--harmonize", type=float, help="0 = true colours, 1 = fully snapped to master palette")
    ap.add_argument("--min-part", type=float, default=0.004, help="drop detached bits smaller than this fraction of the subject")
    ap.add_argument("--colors", type=int, help="max colours used in this asset")
    ap.add_argument("--mode", choices=["kcentroid", "majority", "average"])
    ap.add_argument("--dither", type=float)
    ap.add_argument("--outline", choices=["selective", "dark", "none"])
    ap.add_argument("--bg", help="auto (plain backdrop) | ai (busy scene, needs rembg) | keep | #rrggbb")
    ap.add_argument("--tol", type=float, default=18.0, help="background colour tolerance")
    ap.add_argument("--contrast", type=float, default=0.02, help="line/highlight preservation in majority mode")
    ap.add_argument("--enhance", type=float, default=1.0, help="pre-contrast boost")
    ap.add_argument("--anchor", default="bottom", choices=["bottom", "center"])
    ap.add_argument("--no-clean", action="store_true")
    ap.add_argument("--source", default="painted", choices=["painted", "pixel"],
                    help="painted: illustrations/renders (value stretch, smoothing, average downscale). "
                         "pixel: art that is already pixel art (k-centroid, no smoothing)")
    ap.add_argument("--smooth", type=float, default=1.0, help="painted-source texture smoothing strength")
    ap.add_argument("--no-levels", action="store_true", help="skip value stretch")
    ap.add_argument("--gamma", type=float, default=0.8, help="<1 lifts mid-tones")
    ap.add_argument("--chroma", type=float, default=1.15, help="colour boost before palette mapping")
    ap.add_argument("--sharpen", type=float, default=1.0)
    ap.add_argument("--keep-holes", action="store_true", help="don't cut enclosed background-coloured gaps")
    ap.add_argument("--out", default="pixel_out"); ap.add_argument("--preview", type=int, default=6)
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    cfg = dict(PRESETS[a.preset])
    if a.width or a.height: cfg["size"] = (a.width, a.height)
    if a.source == "painted":
        cfg.update(mode="average", dither=0.0)
    for k in ("colors", "mode", "dither", "outline", "bg"):
        if getattr(a, k) is not None: cfg[k] = getattr(a, k)
    cfg.setdefault("harmonize", 0.3)
    if a.harmonize is not None: cfg["harmonize"] = a.harmonize
    cfg.update(smooth=a.smooth if a.source == "painted" else 0, clean_passes=2 if a.source == "painted" else 1,
               levels=(not a.no_levels) and a.source == "painted", gamma=a.gamma, chroma=a.chroma, sharpen=a.sharpen, holes=not a.keep_holes, min_part=a.min_part, tol=a.tol, contrast=a.contrast, enhance=a.enhance, clean=not a.no_clean,
               anchor="center" if a.preset in ("item", "equipment") else a.anchor)
    items = []
    for p in a.inputs:
        items.append(process(p, cfg, a.palette, a.out, a.preview))
        print("done:", items[-1][0], items[-1][1].size)
    if a.sheet and items: make_sheet(items, a.out)

if __name__ == "__main__":
    main()
