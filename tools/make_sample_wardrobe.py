"""Generate the EXAMPLE wardrobe: simple flat-lay style garment illustrations drawn with Pillow.

These are synthetic illustrations, not photos of any real person's clothes.
Writes sample_wardrobe/<id>.png and sample_wardrobe/wardrobe.json (+ ground_truth.json used
only by tools/eval_describe.py to measure how well vision models describe the images).
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "sample_wardrobe"
S = 4          # supersampling
W = 100        # logical canvas
PX = 480       # final size
BG = (244, 241, 236)


def sh(c, f=0.78):
    return tuple(int(x * f) for x in c)


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Cv:
    def __init__(self):
        self.im = Image.new("RGB", (PX * S // 1, PX * S // 1), BG)
        self.d = ImageDraw.Draw(self.im)
        self.k = PX * S / W

    def p(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def poly(self, pts, fill, outline=None, w=0.7):
        self.d.polygon(self.p(pts), fill=fill, outline=outline or sh(fill, .6), width=int(w * self.k))
        # polygon outline in Pillow is thin; redraw as line for thickness
        self.d.line(self.p(pts + [pts[0]]), fill=outline or sh(fill, .6), width=int(w * self.k), joint="curve")

    def ell(self, box, fill, outline=None, w=0.7):
        b = [box[0] * self.k, box[1] * self.k, box[2] * self.k, box[3] * self.k]
        self.d.ellipse(b, fill=fill, outline=outline or sh(fill, .6), width=int(w * self.k))

    def rect(self, box, fill, outline=None, w=0.7, r=0):
        b = [box[0] * self.k, box[1] * self.k, box[2] * self.k, box[3] * self.k]
        if r:
            self.d.rounded_rectangle(b, radius=r * self.k, fill=fill, outline=outline or sh(fill, .6), width=int(w * self.k))
        else:
            self.d.rectangle(b, fill=fill, outline=outline or sh(fill, .6), width=int(w * self.k))

    def line(self, pts, fill, w=0.7):
        self.d.line(self.p(pts), fill=fill, width=int(w * self.k), joint="curve")

    def done(self, label):
        im = self.im.resize((PX, PX), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        try:
            f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        except Exception:
            f = ImageFont.load_default()
        d.text((10, PX - 22), "EXAMPLE DATA - synthetic illustration", fill=(150, 150, 150), font=f)
        return im


# ---------- garments ----------
def tee(c, col, long_sleeve=False, collar=None, buttons=False, hood=False, cardigan=False, knit=False):
    sl = 52 if long_sleeve else 30
    body = [(34, 22), (42, 20), (50, 25), (58, 20), (66, 22), (88, sl), (80, sl + 10 if not long_sleeve else sl + 4),
            (68, 36 if not long_sleeve else 38), (68, 84), (32, 84), (32, 36 if not long_sleeve else 38),
            (20, sl + 10 if not long_sleeve else sl + 4), (12, sl)]
    if long_sleeve:
        body = [(34, 22), (42, 20), (50, 25), (58, 20), (66, 22), (80, 30), (92, 78), (82, 80), (70, 46), (68, 84),
                (32, 84), (30, 46), (18, 80), (8, 78), (20, 30)]
    c.poly(body, col)
    if hood:
        c.poly([(36, 22), (42, 12), (50, 10), (58, 12), (64, 22), (58, 30), (50, 34), (42, 30)], sh(col, .88))
        c.line([(46, 34), (46, 50)], sh(col, .6), 0.8)
        c.line([(54, 34), (54, 50)], sh(col, .6), 0.8)
        c.rect((38, 62, 62, 78), sh(col, .92), r=2)
    elif collar:
        c.poly([(42, 20), (50, 34), (45, 36), (38, 24)], collar)
        c.poly([(58, 20), (50, 34), (55, 36), (62, 24)], collar)
    else:
        c.d.arc([42 * c.k, 14 * c.k, 58 * c.k, 32 * c.k], 0, 180, fill=sh(col, .6), width=int(.8 * c.k))
    if buttons:
        c.line([(50, 34), (50, 84)], sh(col, .65), .6)
        for y in range(40, 82, 9):
            c.ell((49, y, 51.2, y + 2.2), (250, 250, 250))
    if cardigan:
        c.line([(50, 25), (50, 84)], sh(col, .6), .9)
        for y in range(34, 80, 11):
            c.ell((46.5, y, 49, y + 2.5), (120, 90, 60))
    if knit:
        for x in range(36, 66, 4):
            c.line([(x, 30), (x, 80)], sh(col, .9), .35)
        c.rect((32, 80, 68, 84), sh(col, .85))


def jacket(c, col, lapel=None, buttons=2, pockets=True, puffer=False):
    body = [(32, 20), (42, 17), (50, 22), (58, 17), (68, 20), (84, 28), (92, 80), (82, 82), (70, 46), (70, 88),
            (30, 88), (30, 46), (18, 82), (8, 80), (16, 28)]
    c.poly(body, col)
    c.line([(50, 22), (50, 88)], sh(col, .6), .8)
    if puffer:
        for y in range(30, 88, 12):
            c.line([(30, y), (70, y)], sh(col, .65), .7)
        for y in range(34, 80, 12):
            c.line([(14, y + 2), (24, y + 24)], sh(col, .7), .6)
            c.line([(86, y + 2), (76, y + 24)], sh(col, .7), .6)
        c.rect((43, 17, 57, 24), sh(col, .85))
        return
    if lapel:
        c.poly([(42, 17), (50, 50), (40, 38), (34, 22)], lapel)
        c.poly([(58, 17), (50, 50), (60, 38), (66, 22)], lapel)
    for i in range(buttons):
        c.ell((52, 54 + i * 10, 54.4, 56.4 + i * 10), sh(col, .5))
    if pockets:
        c.rect((34, 66, 44, 68.2), sh(col, .65))
        c.rect((56, 66, 66, 68.2), sh(col, .65))


def trousers(c, col, jeans=False, shorts=False):
    if shorts:
        pts = [(30, 22), (70, 22), (74, 62), (53, 62), (50, 42), (47, 62), (26, 62)]
    else:
        pts = [(32, 12), (68, 12), (72, 92), (55, 92), (50, 40), (45, 92), (28, 92)]
    c.poly(pts, col)
    c.rect((32 if not shorts else 30, 12 if not shorts else 22, 68 if not shorts else 70, 18 if not shorts else 28), sh(col, .88))
    for x in range(36, 66, 8):
        c.rect((x, 12 if not shorts else 22, x + 2.5, 14.5 if not shorts else 24.5), sh(col, .55), w=.3)
    c.line([(50, 18 if not shorts else 28), (50, 40)], sh(col, .6), .6)
    if jeans:
        c.line([(36, 20), (36, 30)], (230, 200, 120), .4)
        c.line([(64, 20), (64, 30)], (230, 200, 120), .4)
        c.line([(31, 90), (47, 90)], (230, 200, 120), .4)
        c.line([(53, 90), (69, 90)], (230, 200, 120), .4)


def skirt(c, col):
    c.poly([(36, 18), (64, 18), (82, 90), (18, 90)], col)
    c.rect((36, 18, 64, 24), sh(col, .85))
    for x in range(24, 80, 6):
        t = (x - 50) / 50
        c.line([(50 + (x - 50) * 0.45, 26), (x, 90)], sh(col, .82), .35)


def dress(c, col, sleeveless=False, belt=None, sleeves=False):
    pts = [(38, 10), (44, 10), (50, 22), (56, 10), (62, 10), (66, 34), (60, 46), (80, 92), (20, 92), (40, 46), (34, 34)]
    c.poly(pts, col)
    if sleeves:
        c.poly([(34, 12), (24, 38), (32, 42), (37, 24)], sh(col, .95))
        c.poly([(66, 12), (76, 38), (68, 42), (63, 24)], sh(col, .95))
    c.poly([(44, 10), (50, 22), (56, 10)], BG, outline=sh(col, .6))
    if belt:
        c.rect((40, 44, 60, 49), belt)
    for x in range(26, 76, 7):
        c.line([(50 + (x - 50) * 0.4, 50), (x, 91)], sh(col, .85), .3)


def shoe_side(c, col, kind):
    if kind == "sneaker":
        c.poly([(12, 62), (30, 40), (46, 44), (62, 56), (88, 62), (90, 76), (12, 76)], col)
        c.rect((10, 74, 92, 82), (250, 250, 250), r=3)
        c.line([(34, 46), (48, 56)], sh(col, .6), .8)
        c.line([(30, 52), (42, 61)], sh(col, .6), .8)
        c.line([(26, 58), (36, 66)], sh(col, .6), .8)
    elif kind == "boot":
        c.poly([(24, 14), (50, 14), (52, 54), (86, 64), (90, 80), (24, 80)], col)
        c.rect((22, 78, 92, 86), sh(col, .5))
        c.rect((22, 78, 34, 94), sh(col, .5))
    elif kind == "heel":
        c.poly([(14, 38), (30, 30), (44, 52), (84, 62), (90, 70), (50, 70), (24, 60), (16, 50)], col)
        c.poly([(18, 52), (26, 70), (30, 70), (24, 52)], sh(col, .6))
        c.poly([(22, 56), (22, 84), (27, 84), (28, 58)], sh(col, .6))
    elif kind == "flat":
        c.poly([(12, 66), (30, 56), (50, 62), (78, 56), (92, 66), (92, 76), (12, 76)], col)
        c.rect((10, 74, 94, 80), sh(col, .6), r=2)
        c.ell((34, 56, 54, 64), BG)
    elif kind == "loafer":
        c.poly([(12, 62), (30, 52), (50, 56), (70, 56), (90, 66), (92, 76), (12, 76)], col)
        c.rect((10, 74, 94, 82), sh(col, .5), r=2)
        c.rect((46, 56, 66, 61), sh(col, .65))
        c.ell((54, 57, 58, 60), (210, 180, 90))
        # suede texture dots
        import random
        r = random.Random(3)
        for _ in range(180):
            x, y = r.uniform(16, 86), r.uniform(60, 73)
            c.ell((x, y, x + .7, y + .7), sh(col, .85), outline=sh(col, .85), w=0)
    elif kind == "rainboot":
        c.poly([(26, 12), (52, 12), (54, 56), (84, 64), (90, 80), (26, 80)], col)
        c.rect((24, 78, 92, 86), sh(col, .55))
        c.rect((26, 12, 52, 20), sh(col, .85))
        c.line([(30, 24), (30, 70)], (255, 250, 200), 1.2)


ITEMS = [
    # id, category, name, drawing fn, truth
    dict(id="white-tee", cat="top", fn=lambda c: tee(c, hexc("#f7f7f5")), type="t-shirt", color="white", warmth=1, formality=1, season=["spring", "summer", "autumn"], material="cotton"),
    dict(id="blue-oxford-shirt", cat="top", fn=lambda c: tee(c, hexc("#a9c7e8"), long_sleeve=True, collar=hexc("#bcd4ee"), buttons=True), type="button-up shirt", color="light blue", warmth=2, formality=3, season=["spring", "autumn", "summer"], material="cotton"),
    dict(id="grey-knit-sweater", cat="top", fn=lambda c: tee(c, hexc("#8b8f94"), long_sleeve=True, knit=True), type="knit sweater", color="grey", warmth=4, formality=2, season=["autumn", "winter"], material="wool knit"),
    dict(id="mustard-hoodie", cat="top", fn=lambda c: tee(c, hexc("#d9a232"), long_sleeve=True, hood=True), type="hoodie", color="mustard yellow", warmth=3, formality=1, season=["spring", "autumn"], material="cotton fleece"),
    dict(id="cream-cardigan", cat="top", fn=lambda c: tee(c, hexc("#efe3c8"), long_sleeve=True, cardigan=True, knit=True), type="cardigan", color="cream", warmth=3, formality=3, season=["spring", "autumn", "winter"], material="knit"),
    dict(id="black-blazer", cat="outer", fn=lambda c: jacket(c, hexc("#26262b"), lapel=hexc("#3a3a40")), type="blazer", color="black", warmth=2, formality=5, season=["spring", "autumn", "winter"], material="wool blend"),
    dict(id="beige-trench", cat="outer", fn=lambda c: jacket(c, hexc("#cdb48c"), lapel=hexc("#d8c4a0"), buttons=4, pockets=True), type="trench coat", color="beige", warmth=3, formality=4, season=["spring", "autumn"], material="cotton gabardine, water-resistant"),
    dict(id="olive-puffer", cat="outer", fn=lambda c: jacket(c, hexc("#66704a"), puffer=True), type="puffer jacket", color="olive green", warmth=5, formality=1, season=["winter"], material="nylon, down fill"),
    dict(id="denim-jacket", cat="outer", fn=lambda c: jacket(c, hexc("#5a7fa8"), lapel=hexc("#6b8fb8"), buttons=4), type="denim jacket", color="blue", warmth=2, formality=1, season=["spring", "autumn"], material="denim"),
    dict(id="blue-jeans", cat="bottom", fn=lambda c: trousers(c, hexc("#456a9a"), jeans=True), type="jeans", color="blue", warmth=3, formality=2, season=["spring", "autumn", "winter"], material="denim"),
    dict(id="black-trousers", cat="bottom", fn=lambda c: trousers(c, hexc("#2b2b30")), type="tailored trousers", color="black", warmth=3, formality=4, season=["spring", "autumn", "winter"], material="wool blend"),
    dict(id="khaki-shorts", cat="bottom", fn=lambda c: trousers(c, hexc("#c2ae83"), shorts=True), type="shorts", color="khaki", warmth=1, formality=1, season=["summer"], material="cotton"),
    dict(id="burgundy-skirt", cat="bottom", fn=lambda c: skirt(c, hexc("#7b2d3e")), type="pleated midi skirt", color="burgundy", warmth=2, formality=3, season=["spring", "autumn", "winter"], material="polyester"),
    dict(id="navy-dress", cat="dress", fn=lambda c: dress(c, hexc("#1f2f56"), sleeves=True, belt=hexc("#c9a24a")), type="dress", color="navy", warmth=2, formality=4, season=["spring", "autumn"], material="crepe"),
    dict(id="yellow-sundress", cat="dress", fn=lambda c: dress(c, hexc("#f2cf4f")), type="sundress", color="yellow", warmth=1, formality=2, season=["summer"], material="cotton"),
    dict(id="white-sneakers", cat="shoes", fn=lambda c: shoe_side(c, hexc("#f4f4f2"), "sneaker"), type="sneakers", color="white", warmth=2, formality=1, season=["spring", "summer", "autumn"], material="canvas"),
    dict(id="brown-ankle-boots", cat="shoes", fn=lambda c: shoe_side(c, hexc("#7a4a2a"), "boot"), type="ankle boots", color="brown", warmth=4, formality=3, season=["autumn", "winter"], material="leather"),
    dict(id="black-heels", cat="shoes", fn=lambda c: shoe_side(c, hexc("#1c1c1f"), "heel"), type="high heels", color="black", warmth=1, formality=5, season=["spring", "summer", "autumn"], material="patent leather"),
    dict(id="tan-suede-loafers", cat="shoes", fn=lambda c: shoe_side(c, hexc("#b88a5a"), "loafer"), type="loafers", color="tan", warmth=2, formality=3, season=["spring", "summer", "autumn"], material="suede"),
    dict(id="yellow-rain-boots", cat="shoes", fn=lambda c: shoe_side(c, hexc("#f0c419"), "rainboot"), type="rain boots", color="yellow", warmth=3, formality=1, season=["spring", "autumn", "winter"], material="rubber"),
    dict(id="black-flats", cat="shoes", fn=lambda c: shoe_side(c, hexc("#2a2a2e"), "flat"), type="ballet flats", color="black", warmth=1, formality=4, season=["spring", "summer", "autumn"], material="leather"),
]


def main():
    OUT.mkdir(exist_ok=True)
    wardrobe, truth = [], {}
    for it in ITEMS:
        c = Cv()
        it["fn"](c)
        c.done(it["id"]).save(OUT / f"{it['id']}.png", optimize=True)
        wardrobe.append({"id": it["id"], "image": f"{it['id']}.png"})
        truth[it["id"]] = {k: it[k] for k in ("cat", "type", "color", "warmth", "formality", "season", "material")}
    (OUT / "wardrobe.json").write_text(json.dumps({"_note": "EXAMPLE DATA: synthetic illustrations, not real clothes", "items": wardrobe}, indent=2))
    (OUT / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    # contact sheet for docs
    cols = 5
    rows = (len(ITEMS) + cols - 1) // cols
    th = 200
    sheet = Image.new("RGB", (cols * th, rows * th), BG)
    for i, it in enumerate(ITEMS):
        im = Image.open(OUT / f"{it['id']}.png").resize((th, th))
        sheet.paste(im, ((i % cols) * th, (i // cols) * th))
    (OUT.parent / "docs").mkdir(exist_ok=True)
    sheet.save(OUT.parent / "docs" / "sample_wardrobe_sheet.png")
    print("wrote", len(ITEMS), "items")


if __name__ == "__main__":
    main()
