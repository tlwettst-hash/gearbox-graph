"""Draw the shortcut icon: a generic red 2x2 brick in isometric view.

Usage: python3 make_icon.py --out gearbox-graph.png   (Mac)
       python3 make_icon.py --out gearbox-graph.ico   (Windows, multi-size)
Needs Pillow. Writes one file; touches nothing else.
"""
import argparse
from PIL import Image, ImageDraw

S = 2048                      # drawn at 2x, scaled down for smooth edges
H, SH, SR = 1.2, 0.2, 0.3     # brick height, stud height, stud radius (in stud pitches)
U = S * 0.84 / 3.464          # pixels per stud pitch; the brick is 2*sqrt(3) pitches wide
CX, CY = S / 2, S / 2 - (2 - H - SH) / 2 * U   # centre the brick vertically

TOP, LEFT, RIGHT = (232, 48, 42), (199, 26, 18), (150, 18, 12)
STUD_SIDE, EDGE = (176, 20, 14), (90, 8, 5)


def p(x, y, z):  # isometric projection
    return (CX + (x - y) * 0.866 * U, CY + (x + y) * 0.5 * U - z * U)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    out = ap.parse_args().out
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(2, int(U * 0.02))
    d.polygon([p(0, 2, 0), p(2, 2, 0), p(2, 2, H), p(0, 2, H)], fill=LEFT, outline=EDGE, width=w)
    d.polygon([p(2, 0, 0), p(2, 2, 0), p(2, 2, H), p(2, 0, H)], fill=RIGHT, outline=EDGE, width=w)
    d.polygon([p(0, 0, H), p(2, 0, H), p(2, 2, H), p(0, 2, H)], fill=TOP, outline=EDGE, width=w)
    ax, ay = SR * 1.2247 * U, SR * 0.7071 * U   # a flat circle seen isometrically
    for sx, sy in [(0.5, 0.5), (1.5, 0.5), (0.5, 1.5), (1.5, 1.5)]:   # back to front
        bx, by = p(sx, sy, H)
        tx, ty = p(sx, sy, H + SH)
        d.ellipse([bx - ax, by - ay, bx + ax, by + ay], fill=STUD_SIDE, outline=EDGE, width=w)
        d.rectangle([bx - ax, ty, bx + ax, by], fill=STUD_SIDE)
        d.line([(bx - ax, ty), (bx - ax, by)], fill=EDGE, width=w)
        d.line([(bx + ax, ty), (bx + ax, by)], fill=EDGE, width=w)
        d.ellipse([tx - ax, ty - ay, tx + ax, ty + ay], fill=TOP, outline=EDGE, width=w)
        d.ellipse([tx - ax * .55, ty - ay * .75, tx - ax * .05, ty - ay * .15], fill=(245, 110, 100))  # shine
    img = img.resize((S // 2, S // 2), Image.LANCZOS)
    if out.lower().endswith(".ico"):   # Windows icon: every size Explorer asks for
        img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    else:
        img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
