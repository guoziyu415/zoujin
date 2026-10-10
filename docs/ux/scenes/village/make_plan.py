# Draws docs/ux/scenes/village/plan.svg from the coordinates in docs/ux/scenes/village.md.
# Usage: python3 -I make_plan.py plan.svg   (change a coordinate here and in village.md together)
import math, sys
out = sys.argv[1]
W = 924
parts = []
FONT = "font-family=\"'Noto Sans CJK SC','PingFang SC','Hiragino Sans','Microsoft YaHei',sans-serif\""
C = dict(bg='#fbfaf6', ink='#2b2a26', mute='#6d6a60', road='#e6d9b9', roadedge='#c9b98f',
         grass='#e9e3c4', rock='#bdb7aa', rockedge='#8f897b', tree='#7d8f5c', treeedge='#55663b',
         calm='#7d9bb3', flood='#a98a5c', bar='#d3cbb8', wood='#8a7458', melos='#a8742c',
         player='#2f4f7a', cam='#8c8c8c', sun='#c99700', shadow='#9a9686', bandit='#5b5248')

def text(x, y, s, size=12, color=None, anchor='start', weight='normal'):
    parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color or C["ink"]}" text-anchor="{anchor}" font-weight="{weight}" {FONT}>{s}</text>')

class Plan:
    def __init__(self, ox, oy, s, x0, x1, y0, y1, az, title):
        self.ox, self.oy, self.s = ox, oy, s
        self.x0, self.x1, self.y0, self.y1, self.az = x0, x1, y0, y1, az
        w, h = (x1 - x0) * s, (y1 - y0) * s
        parts.append(f'<rect x="{ox}" y="{oy}" width="{w}" height="{h}" fill="{C["grass"]}" stroke="{C["mute"]}" stroke-width="1"/>')
        text(ox, oy - 10, title, 15, weight='bold')
    def P(self, x, y):
        return self.ox + (x - self.x0) * self.s, self.oy + (self.y1 - y) * self.s
    def poly(self, pts, fill, stroke='none', sw=1, dash=None, op=1):
        d = ' '.join(f'{a:.1f},{b:.1f}' for a, b in (self.P(x, y) for x, y in pts))
        da = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da} fill-opacity="{op}"/>')
    def line(self, pts, stroke, sw=1.5, dash=None, op=1):
        d = ' '.join(f'{a:.1f},{b:.1f}' for a, b in (self.P(x, y) for x, y in pts))
        da = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"{da} stroke-opacity="{op}" stroke-linecap="round" stroke-linejoin="round"/>')
    def rect(self, xa, ya, xb, yb, fill, stroke='none', sw=1, dash=None, op=1):
        self.poly([(xa, ya), (xb, ya), (xb, yb), (xa, yb)], fill, stroke, sw, dash, op)
    def circle(self, x, y, r_m, fill, stroke='none', sw=1, op=1, r_px=None):
        a, b = self.P(x, y)
        r = r_px if r_px else r_m * self.s
        parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" fill-opacity="{op}"/>')
    def label(self, x, y, s, dx=6, dy=4, size=11, color=None, anchor='start'):
        a, b = self.P(x, y)
        text(a + dx, b + dy, s, size, color, anchor)
    def spot(self, x, y, name, who, facing=None, dx=7, dy=4, anchor='start'):
        col = C['melos'] if who == 'm' else C['player'] if who == 'p' else C['mute']
        a, b = self.P(x, y)
        if facing is not None:
            fx, fy = facing
            a2, b2 = self.P(x + fx * 2.2, y + fy * 2.2)
            parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b2:.1f}" stroke="{col}" stroke-width="2"/>')
        if who == 'p':
            parts.append(f'<rect x="{a-4.5:.1f}" y="{b-4.5:.1f}" width="9" height="9" fill="{col}"/>')
        else:
            parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4.5" fill="{col}"/>')
        text(a + dx, b + dy, name, 10.5, col, anchor)
    def cam(self, x, y, fx, fy):
        a, b = self.P(x, y)
        ang = math.atan2(-fy, fx)
        pts = []
        for da, r in ((0, 8), (2.5, 6), (-2.5, 6)):
            pts.append((a + r * math.cos(ang + da), b + r * math.sin(ang + da)))
        parts.append('<polygon points="' + ' '.join(f'{p:.1f},{q:.1f}' for p, q in pts) + f'" fill="{C["cam"]}"/>')
    def vec(self, theta):  # compass bearing -> plan unit vector
        d = math.radians(theta - self.az)
        return math.cos(d), -math.sin(d)
    def compass(self, x, y):
        nx, ny = self.vec(0)
        a, b = self.P(x, y); a2, b2 = self.P(x + nx * 4, y + ny * 4)
        parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b2:.1f}" stroke="{C["ink"]}" stroke-width="1.5" marker-end="url(#ah)"/>')
        a3, b3 = self.P(x + nx * 5.6, y + ny * 5.6)
        text(a3, b3 + 4, 'N', 11, anchor='middle', weight='bold')
        text(a, b + 22, f'+x = {self.az}°', 10, C['mute'], 'middle')
    def sun(self, x, y, theta, label):
        vx, vy = self.vec(theta)
        a, b = self.P(x + vx * 5, y + vy * 5); a2, b2 = self.P(x, y)
        parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b2:.1f}" stroke="{C["sun"]}" stroke-width="2" marker-end="url(#sh)"/>')
        parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="5" fill="{C["sun"]}"/>')
        text(a, b - 8, label, 10, C['sun'], 'middle')
    def tree(self, x, y, r, label=None):
        self.circle(x, y, r, C['tree'], C['treeedge'], 1, 0.55)
        self.circle(x, y, 0, C['treeedge'], r_px=2)
        if label: self.label(x, y, label, dx=r * self.s * 0.7 + 2, size=10, color=C['treeedge'])
    def scalebar(self, x, y, m=10):
        a, b = self.P(x, y); a2, _ = self.P(x + m, y)
        parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b:.1f}" stroke="{C["ink"]}" stroke-width="2"/>')
        text((a + a2) / 2, b - 5, f'{m} m', 10, anchor='middle')

def road(p, xa, xb, y, w):
    p.rect(xa, y - w / 2, xb, y + w / 2, C['road'], C['roadedge'], 1)


C.update(wall='#9d9584', house='#d6c7a6', roof='#c58a5c', wheat='#e7d68f', pasture='#dfe3bf', vine='#7d9150', floor='#d9d0bb')
V = Plan(30, 64, 12, -36, 36, -26, 26, 90, '村子（+x = 90°，正东）')
V.rect(14, -26, 36, -3, C['wheat'], op=0.9)
V.rect(-36, -26, -16, -16, C['wheat'], op=0.9)
V.label(26, -20, '麦田（收麦的人）', dx=0, dy=4, size=11, anchor='middle', color=C['mute'])
V.label(-26, -21, '麦田', dx=0, dy=4, size=11, anchor='middle', color=C['mute'])
V.rect(6, 5, 32, 24, C['pasture'], C['wall'], 2.5)
V.label(26, 21, '牧场', dx=0, dy=4, size=12, anchor='middle', color=C['mute'])
V.rect(-34, 19, -16, 26, '#e3e6c6')
for y in (20, 21.5, 23, 24.5):
    V.line([(-33.5, y), (-16.5, y)], C['vine'], 2.2)
V.label(-25, 25.3, '葡萄园（青的小葡萄）', dx=0, dy=-1, size=10.5, anchor='middle', color=C['treeedge'])
road(V, -32, 36, 2, 3)
V.label(36, 2, '往锡拉库萨 →', dx=-4, dy=-12, size=10.5, anchor='end', color=C['mute'])
V.label(-29, 2, '小路', dx=0, dy=4, size=10.5, anchor='middle', color=C['mute'])
# Melos farmstead
V.rect(-14, -14, 2, -0.5, C['floor'], C['wall'], 3)
V.line([(-7.5, -0.5), (-5.5, -0.5)], C['floor'], 5)
V.rect(-14, -14, -2, -8.5, C['house'], C['ink'], 1.5)
V.label(-7, -10, '屋子（屋里能进：宴席）', dx=0, dy=4, size=10.5, anchor='middle')
V.circle(-8, -11.5, 0, '#c97b3b', r_px=4)
V.line([(-8.6, -8.5), (-7.4, -8.5)], C['house'], 4)
V.rect(-6.6, -4.9, -5.4, -4.1, C['rock'], C['rockedge'], 1.2)
V.label(-6, -4.5, '祭坛', dx=10, dy=4, size=10.5)
V.tree(-11.5, -3, 3)
V.label(-11.5, -3, '无花果', dx=-40, dy=4, size=10, color=C['treeedge'], anchor='end')
V.rect(2, -14, 12, -3, '#e6dfc8', C['wall'], 2.5)
V.line([(6.4, -3), (7.6, -3)], '#e6dfc8', 4)
V.line([(2, -10.6), (2, -11.4)], C['floor'], 4)
V.rect(2, -14, 7, -10, '#cdb98d', C['ink'], 1.2)
V.line([(2, -10), (7, -10)], '#e6dfc8', 2, '3 2')
V.label(4.5, -10.8, '羊舍', dx=0, dy=4, size=10.5, anchor='middle')
V.label(9.5, -6.5, '羊圈', dx=0, dy=4, size=10.5, anchor='middle', color=C['mute'])
V.label(-8, -14, '梅洛斯家', dx=0, dy=16, size=11.5, anchor='middle', weight='bold') if False else V.label(-6, -14, '梅洛斯家', dx=0, dy=16, size=11.5, anchor='middle')
# neighbours, well
V.rect(-12, 5, -4, 11, C['house'], C['ink'], 1)
V.rect(-2, 7, 4, 12, C['house'], C['ink'], 1)
V.label(-8, 8, '邻居 A', dx=0, dy=4, size=10, anchor='middle', color=C['mute'])
V.label(1, 9.5, '邻居 B', dx=0, dy=4, size=10, anchor='middle', color=C['mute'])
V.circle(4, 4.5, 0.7, '#9cc0d6', C['rockedge'], 1.2)
V.label(4, 4.5, '井', dx=7, dy=4, size=10.5)
# groom
V.rect(-32, 5, -18, 18, C['floor'], C['wall'], 3)
V.line([(-21.8, 5), (-20.2, 5)], C['floor'], 5)
V.rect(-32, 13, -20, 18, C['house'], C['ink'], 1.5)
V.label(-26, 15.5, '花婿家', dx=0, dy=4, size=11.5, anchor='middle')
V.rect(-30, 7, -22, 11.5, C['vine'], C['treeedge'], 1, '3 2', 0.35)
V.label(-29.6, 11, '葡萄架', dx=0, dy=8, size=10, color=C['treeedge'])
V.rect(-27.2, 8.6, -24.8, 9.4, C['wood'], C['ink'], 0.8)
# threshing floor
V.circle(-26, -10, 5, '#e8e1cf', C['rockedge'], 2)
V.label(-26, -10, '打谷场（高 1.5 m，朝西看日没）', dx=0, dy=4, size=10, anchor='middle')
V.line([(-24, 0.5), (-25, -5)], C['roadedge'], 3, '5 3')
# place.melos-home polygon (layout places)
V.line([(-14, -14), (12, -14), (12, -0.5), (32, -0.5), (32, 24), (6, 24), (6, 3.5), (-14, 3.5), (-14, -14)], '#7a3b6b', 1.6, '7 4', 0.75)
V.label(31.6, 23.2, 'place.melos-home', dx=0, dy=12, size=10, color='#7a3b6b', anchor='end')
# spots
V.spot(24, -1.5, 'field-edge 牧童开局', 'p', (-1, 0), dx=-4, dy=18)
V.cam(33, -1.5, -1, 0)
V.spot(20, 2, 'road-arrive 跟着到村', 'p', (-1, 0), dx=-4, dy=-10)
V.cam(29, 2, -1, 0)
V.spot(16, 13, 'sister-sheep 妹妹和羊', 'n', dx=7, dy=4)
for (x, y) in ((14, 15), (17.5, 15.5), (15, 11), (18.5, 12), (13, 12.5), (19.5, 14), (16.5, 16.8)):
    V.circle(x, y, 0, '#ffffff', C['mute'], 1, r_px=3)
V.spot(12, 3, 'melos-meet', 'm', (-1, 0), dx=6, dy=-8)
V.spot(10.7, 3.3, 'sister-meet', 'n', (1, 0), dx=-7, dy=16, anchor='end')
V.spot(-6, -3.2, '', 'm', (0, -1))
V.label(-6, -3.2, 'melos-altar', dx=8, dy=-6, size=10, color=C['melos'])
V.spot(-6, -6, 'wedding-melos', 'm', (0, 1), dx=8, dy=4)
V.spot(-11, -12.5, '', 'm')
V.label(-11, -12.5, 'melos-sleep', dx=-7, dy=4, size=10, color=C['melos'], anchor='end')
V.spot(-27, 9.5, '', 'n', (1, 0)); V.spot(-24.5, 9.5, '', 'm', (-1, 0))
V.label(-25.8, 9.5, 'groom-table · melos-groom（夜，油灯）', dx=0, dy=20, size=10, color=C['melos'], anchor='middle')
V.spot(4.5, -12.5, '', 'm')
V.label(4.5, -12.5, 'melos-hut', dx=0, dy=24, size=10, color=C['melos'], anchor='middle')
V.label(36, 2, 'way.east', dx=-4, dy=18, size=10, color=C['mute'], anchor='end')
V.line([(4.5, -12.5), (7, -3), (12, 1.5), (36, 1.5)], C['melos'], 1.3, '5 3', 0.8)
V.label(20, 0, '三日目 04:30 冒雨跑出去', dx=0, dy=-2, size=9.5, color=C['melos'], anchor='middle')
V.compass(-32, -20)
V.sun(30, -8, 116, '10:00')
V.sun(-30, -1, 294, '19:00 日没')
V.sun(0, -20, 180, '12:00 婚礼')
V.scalebar(16, -24.5)
H = 64 + 52 * 12 + 120
lx = 30
ly = 64 + 52 * 12 + 30
notes = ['坐标单位米，+x 朝东。方块 = 玩家落地点（短线是朝向），灰三角 = 落地时默认镜头（背后 9 m），褐点 = 梅洛斯的位置点，太阳圆点 = 太阳从这边来。',
         '屋子是这个场景唯一的室内（二日目夜的宴席）。羊舍朝北敞开，花婿家的夜谈在葡萄架下（室外）。',
         '牧童从 field-edge 开始（一日目 09:00，第一屏朝西看村子，顺光）；跟梅洛斯走夜路的人一日目 10:00 到 road-arrive。',
         '紫虚线 = place.melos-home 的多边形（含门前的路和牧场，village.md 2.1）。细节见 village.md。']
for i, n in enumerate(notes):
    text(lx, ly + 18 * i, n, 11.5, C['mute'])
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#2b2a26"/></marker>'
       '<marker id="sh" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#c99700"/></marker></defs>'
       f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>'
       f'<text x="30" y="28" font-size="19" font-weight="bold" fill="{C["ink"]}" {FONT}>村子的平面（v1.0，2026-10-10）</text>'
       + ''.join(parts) + '</svg>')
open(out, 'w', encoding='utf-8').write(svg)
print('ok', W, H)
