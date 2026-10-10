# Draws docs/ux/scenes/castle/plan.svg from the coordinates in docs/ux/scenes/castle.md.
# Usage: python3 -I make_plan.py plan.svg   (change a coordinate here and in castle.md together)
import math, sys
out = sys.argv[1]
W = 880
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



C.update(wall='#6f685a', stone='#e4dccb', open_='#f1ecdf', roof='#d2c8b2', hall='#cfc4ad', dais='#b9ab8f',
         curtain='#3d3b66', water='#9cc0d6', fire='#c9622b', shade='#7c7666')
K = Plan(30, 70, 14, -34, 24, -13, 16, 90, '王城（+x = 90°，正东；西边是广场）')
# outside: plaza side and the hill
K.rect(-34, -13, -30, 16, '#e7dfc9')
K.label(-32, 13, '广场', dx=0, dy=4, size=11, anchor='middle', color=C['mute'])
K.label(-32, 11.4, '的城门', dx=0, dy=4, size=11, anchor='middle', color=C['mute'])
# gate building
K.rect(-30, -10, -24, -2, C['wall'], C['ink'], 1)
K.rect(-30, 2, -24, 10, C['wall'], C['ink'], 1)
K.rect(-30, -2, -24, 2, C['stone'], C['ink'], 0.8)
K.label(-27, -6, '城门', dx=0, dy=4, size=10.5, anchor='middle', color='#f4efe2')
K.label(-27, 6.6, '墙高 8 m', dx=0, dy=4, size=9.5, anchor='middle', color='#f4efe2')
# courtyard, porticoes (roofed) and open part
K.rect(-24, -10, -6, 10, C['roof'], C['ink'], 1.6)
K.rect(-20, -6, -10, 6, C['open_'], C['mute'], 0.8, '4 3')
K.label(-17.5, -3.2, '中庭（露天）', dx=0, dy=4, size=11, anchor='middle')
K.label(-19.5, 9.0, '北柱廊（两排柱子）', dx=0, dy=4, size=10, anchor='middle', color=C['mute'])
K.label(-15, -8.4, '南柱廊', dx=0, dy=4, size=10, anchor='middle', color=C['mute'])
cols = []
for x in (-20, -17.5, -15, -12.5, -10):
    cols += [(x, 6), (x, -6), (x, 8)]
for y in (-4, -2, 2, 4):
    cols += [(-20, y), (-10, y)]
for x, y in cols:
    K.circle(x, y, 0.3, '#f7f3ea', C['ink'], 1)
K.circle(-15, 0, 1.0, C['water'], C['rockedge'], 1.5)
K.label(-15, 0, '蓄水池', dx=0, dy=-17, size=9.5, anchor='middle', color=C['mute'])
for x, y in ((-25.2, 1.4), (-17, -8.2), (-13, -8.2)):
    K.circle(x, y, 0, C['fire'], r_px=3.5)
# 16:00 wall shadow on the courtyard floor
K.rect(-20, -6, -12.6, 6, C['shade'], op=0.28)
K.line([(-12.6, -6.4), (-12.6, 5.8)], C['shade'], 1.6, '6 3')
K.label(-16.3, -5.2, '三日目 16:00 墙影', dx=0, dy=4, size=9.5, anchor='middle', color=C['shade'])
K.label(-8, -12, '17:00 墙影盖满中庭，然后爬上大门（18:00 约 4 m 高）', dx=0, dy=4, size=9.5, anchor='middle', color=C['shade'])
# throne hall
K.rect(-6.4, -7.4, 16.4, 7.4, C['wall'])
K.rect(-6, -7, 16, 7, C['hall'], C['ink'], 0.6)
K.rect(-6.6, -2, -5.6, 2, C['roof'])
K.label(-6, -2, '大门 4 m', dx=0, dy=-3, size=9.5, anchor='middle', color=C['mute'])
K.label(5.5, 9.6, '王座之间（屋高 8 m，南北墙高处一排窄窗）', dx=0, dy=4, size=11, anchor='middle')
for x in (-3, 1, 5, 9, 13):
    for y in (7.2, -7.2):
        a, b = K.P(x - 0.8, y); a2, _ = K.P(x + 0.8, y)
        parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b:.1f}" stroke="#bfd3e0" stroke-width="3"/>')
K.rect(10, -3.4, 16, 3.4, C['dais'], C['ink'], 0.8)
for x in (10.67, 11.33, 12):
    K.line([(x, -3.4), (x, 3.4)], C['ink'], 0.6)
K.label(11, -3.4, '三级台阶 0.9 m', dx=0, dy=13, size=9.5, anchor='middle')
K.line([(15.5, -3.2), (15.5, 3.2)], C['curtain'], 4)
K.label(15.5, 3.4, '帘子', dx=0, dy=-5, size=9.5, anchor='middle', color=C['curtain'])
K.rect(13, -0.8, 14.3, 0.8, C['wood'], C['ink'], 1)
K.circle(11, 0, 1.1, 'none', C['sun'], 1.2)
K.label(10.5, 3.4, '吊灯 4.5 m', dx=0, dy=-5, size=9.5, anchor='middle', color='#8a6a00')
for y in (2.5, -2.5):
    K.circle(9, y, 0, C['fire'], r_px=3.5)
for x in (-2, 3, 8, 13):
    for y in (4, -4):
        K.circle(x, y, 0.4, '#f7f3ea', C['ink'], 1)
a, b = K.P(16.4, 0.8); a2, _ = K.P(16.4, -0.8)
parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b:.1f}" stroke="#bfd3e0" stroke-width="3"/>')
# tower
K.rect(16.6, 8, 22, 14, C['wall'], C['ink'], 1)
K.label(19.3, 11, '塔', dx=0, dy=4, size=10.5, anchor='middle', color='#f4efe2')
K.label(19.3, 8, '约 30 m', dx=0, dy=14, size=9.5, anchor='middle', color=C['mute'])
# paths
K.line([(5, 0), (-6, 0), (-12, 1.8), (-18, 1.8), (-24, 0), (-33, 0)], C['melos'], 1.3, '5 3', 0.8)
K.line([(-5, -0.6), (3.6, 0.5)], C['mute'], 1.2, '3 3')
# spots
K.spot(-27, 0, 'gate-in', 'p', (1, 0), dx=-2, dy=-9)
K.spot(-25, 0, '', 'm', (1, 0))
K.label(-25, 0, 'melos-led-in', dx=-4, dy=18, size=9.5, color=C['melos'])
K.cam(-29.6, 0, 1, 0)
K.spot(5, 0, '', 'm', (1, 0))
K.label(5, 0, 'before-king', dx=0, dy=-24, size=10, color=C['melos'], anchor='middle')
for y in (1.6, -1.6):
    K.circle(5, y, 0, C['mute'], r_px=3)
K.spot(13.5, 0, '', 'n', (-1, 0))
K.label(13.5, 0, 'king-throne 王', dx=0, dy=22, size=10.5, color=C['ink'], anchor='middle')
K.spot(3.5, -4.8, 'companion-aside', 'p', (0.8, 0.6), dx=-6, dy=16)
for x in (-1, 1.5, 4.5, 6.5, 9.5, 11):
    K.circle(x, 5.5, 0, '#ffffff', C['mute'], 1, r_px=3)
K.label(5, 5.5, 'courtiers 群臣', dx=0, dy=-6, size=9.5, color=C['mute'], anchor='middle')
K.circle(-5, 0, 0, C['mute'], r_px=3)
K.label(-5, -0.6, 'selinuntius-in', dx=6, dy=14, size=9.5, color=C['mute'])
K.spot(4, 0.6, '', 'n')
K.label(4, 0.6, 'selinuntius-meet', dx=-6, dy=-12, size=9.5, color=C['mute'], anchor='end')
K.spot(-12.5, 7.6, '', 'n', (0, -1))
K.line([(-12.5, 8.4), (-12.5, 11.2)], C['ink'], 0.8)
K.label(-12.5, 11.2, 'hostage-column 人质（北柱廊第二排）', dx=0, dy=-4, size=10, color=C['ink'], anchor='middle')
K.spot(-8.5, 9.3, '', 'n')
K.label(-8.5, 9.3, 'guard', dx=7, dy=4, size=9.5, color=C['mute'])
K.spot(-12.5, 5.5, 'hostage-near', 'p', (0, 1), dx=8, dy=11)
K.spot(-14.5, 4.5, '', 'n', (0.54, 0.84))
K.label(-14.5, 4.5, 'hostage-visit', dx=-6, dy=14, size=9.5, color=C['mute'], anchor='end')
K.cam(-12.5, -3.5, 0, 1)
K.label(-33, 0, 'way.plaza', dx=0, dy=-8, size=10, color=C['mute'])
K.compass(19, -8)
K.sun(-27, -11.6, 268, '16:00')
K.scalebar(6, -12.2)
H = 70 + 29 * 14 + 138
lx = 30
ly = 70 + 29 * 14 + 34
notes = ['坐标单位米，+x 朝东。方块 = 玩家落地点（短线是朝向），灰三角 = 落地时的镜头，褐点 = 梅洛斯，灰点 = 别的角色，白圈 = 柱子，橙点 = 火盆。',
         '浅褐 = 有顶的柱廊，虚线框 = 露天。灰影 = 三日目 16:00 西墙的影子（太阳高 35°，墙 8 m，影长约 11 m，正好到人质正前方）。',
         '褐虚线 = 梅洛斯的路（示意，前端沿导航网格演）：从 melos-led-in 押到 before-king，23:45 原路出城到 way.plaza。',
         '灰虚线 = セリヌンティウス从 selinuntius-in 走到 selinuntius-meet。能自动站的点只有 king-throne（排第一）和 hostage-visit。',
         '人质绑在北柱廊第二排的柱子上，正午也在阴影里。细节见 castle.md。']
for i, n in enumerate(notes):
    text(lx, ly + 18 * i, n, 11.5, C['mute'])
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#2b2a26"/></marker>'
       '<marker id="sh" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#c99700"/></marker></defs>'
       f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>'
       f'<text x="30" y="28" font-size="19" font-weight="bold" fill="{C["ink"]}" {FONT}>王城的平面（v1.0，2026-10-10）</text>'
       + ''.join(parts) + '</svg>')
open(out, 'w', encoding='utf-8').write(svg)
print('ok', W, H)
