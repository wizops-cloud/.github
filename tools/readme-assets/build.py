"""Génère les visuels SVG du README de l'organisation GitHub WizOps.

Chaque SVG embarque un sous-ensemble des polices Sora / DM Sans (GitHub bloque
les polices externes dans <img>), et existe en variante dark et light.
"""
import base64
import io
import json
import re
import sys
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).parent
FONTS = HERE.parent / "fonts"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
ICONS = json.loads((HERE / "icons.json").read_text())
LOGO = (HERE / "logo.svg").read_text()

# --------------------------------------------------------------------------- fonts
FACES = {
    "sora700": ("Sora.ttf", {"wght": 700}),
    "sora600": ("Sora.ttf", {"wght": 600}),
    "dm400": ("DMSans.ttf", {"wght": 400, "opsz": 14}),
    "dm500": ("DMSans.ttf", {"wght": 500, "opsz": 14}),
    "dm700": ("DMSans.ttf", {"wght": 700, "opsz": 14}),
}
_static = {}


def static_font(face):
    if face not in _static:
        file, axes = FACES[face]
        f = TTFont(FONTS / file)
        _static[face] = instancer.instantiateVariableFont(f, axes)
    return _static[face]


def measure(s, face, size):
    f = static_font(face)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    w = 0
    for ch in s:
        g = cmap.get(ord(ch)) or cmap.get(ord("?"))
        w += hmtx[g][0]
    return w * size / upm


def wrap(s, face, size, maxw):
    words, lines, cur = s.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if measure(t, face, size) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def font_css(used):
    css = []
    for face, chars in used.items():
        if not chars:
            continue
        src = io.BytesIO()
        static_font(face).save(src)
        src.seek(0)
        f = TTFont(src)
        opts = subset.Options()
        opts.flavor = "woff"
        opts.layout_features = ["kern", "liga"]
        opts.name_IDs = []
        s = subset.Subsetter(opts)
        s.populate(text="".join(sorted(chars)) + " ")
        s.subset(f)
        buf = io.BytesIO()
        f.flavor = "woff"
        f.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        css.append(f"@font-face{{font-family:'{face}';src:url(data:font/woff;base64,{b64}) format('woff');}}")
    return "".join(css)


# --------------------------------------------------------------------------- themes
THEMES = {
    "dark": dict(
        card="#0E2531", card2="#112C3A", border="#1D4552", text="#ECF7F7", muted="#9DBDC0",
        accent="#F97316", petrol="#3FC1C9", petrol2="#14918F", tint="#14918F26", soft="#3FC1C914",
        star="#F97316",
    ),
    "light": dict(
        card="#FFFFFF", card2="#F4FBFB", border="#CFE9E8", text="#0B1F2A", muted="#4A6468",
        accent="#EA580C", petrol="#127478", petrol2="#14918F", tint="#14918F1A", soft="#14918F0D",
        star="#EA580C",
    ),
}
BRAND = dict(night="#0B1F2A", deep="#071820", p950="#072B31", p800="#0F5D63", p600="#14918F",
             p400="#3FC1C9", orange="#F97316", ink="#ECF7F7", muted="#A9C9CB")


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts, self.defs = [], []
        self.used = {k: set() for k in FACES}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, face, size, fill, anchor="start", ls=0, opacity=1):
        self.used[face].update(s)
        extra = f' letter-spacing="{ls}"' if ls else ""
        op = f' fill-opacity="{opacity}"' if opacity != 1 else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{face}" font-size="{size}" fill="{fill}"'
                 f' text-anchor="{anchor}"{extra}{op}>{escape(s)}</text>')

    def para(self, x, y, s, face, size, fill, maxw, lh=1.45, anchor="start"):
        lines = wrap(s, face, size, maxw)
        for i, line in enumerate(lines):
            self.text(x, y + i * size * lh, line, face, size, fill, anchor)
        return y + len(lines) * size * lh

    def icon(self, kind, name, x, y, size, color, stroke=None):
        body = ICONS[kind][name]
        if stroke:
            body = body.replace('stroke-width="2"', f'stroke-width="{stroke}"')
        body = body.replace("currentColor", color)
        self.add(f'<g transform="translate({x:.1f} {y:.1f}) scale({size / 24:.4f})">{body}</g>')

    def logo(self, x, y, size):
        inner = re.sub(r"^<svg[^>]*>|</svg>\s*$", "", LOGO.strip())
        self.add(f'<g transform="translate({x} {y}) scale({size / 512:.4f})">{inner}</g>')

    def render(self, path):
        css = font_css(self.used)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
               f'<title>{escape(self.title)}</title><style>{css}</style>'
               f'<defs>{"".join(self.defs)}</defs>{"".join(self.parts)}</svg>')
        (OUT / path).write_text(svg)
        print(f"{path:32s} {len(svg) / 1024:6.1f} KB")


def card_bg(svg, t, x, y, w, h, r=28, featured=False):
    gid = f"cg{len(svg.defs)}"
    svg.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
                    f'<stop offset="0" stop-color="{t["card2"]}"/><stop offset="1" stop-color="{t["card"]}"/></linearGradient>')
    svg.add(f'<rect x="{x + 1}" y="{y + 1}" width="{w - 2}" height="{h - 2}" rx="{r}" fill="url(#{gid})" '
            f'stroke="{t["border"]}" stroke-width="2"/>')
    if featured:
        svg.add(f'<rect x="{x + 1}" y="{y + 1}" width="{w - 2}" height="{h - 2}" rx="{r}" fill="none" '
                f'stroke="{t["petrol2"]}" stroke-opacity=".55" stroke-width="2"/>')


def icon_tile(svg, t, kind, name, x, y, s=76):
    svg.add(f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="20" fill="{t["tint"]}"/>')
    svg.icon(kind, name, x + s * 0.22, y + s * 0.22, s * 0.56, t["petrol"], stroke=1.75)


def network_pattern(svg, w, h, seed=7, opacity=0.18):
    import random
    rnd = random.Random(seed)
    pts = [(rnd.uniform(0, w), rnd.uniform(0, h)) for _ in range(26)]
    g = []
    for i, (x1, y1) in enumerate(pts):
        for x2, y2 in pts[i + 1:]:
            if (x1 - x2) ** 2 + (y1 - y2) ** 2 < 260 ** 2:
                g.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}"/>')
    svg.add(f'<g stroke="{BRAND["p400"]}" stroke-opacity="{opacity}" stroke-width="1.5">{"".join(g)}</g>')
    for i, (x, y) in enumerate(pts):
        c = BRAND["orange"] if i % 5 == 0 else BRAND["p400"]
        svg.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{4 if i % 5 == 0 else 3}" fill="{c}" fill-opacity="{opacity * 3:.2f}"/>')


def brand_bg(svg, w, h, r=32):
    svg.defs.append('<linearGradient id="bb" x1="0" y1="0" x2="1" y2="1">'
                    f'<stop offset="0" stop-color="{BRAND["deep"]}"/><stop offset=".55" stop-color="{BRAND["night"]}"/>'
                    f'<stop offset="1" stop-color="{BRAND["p950"]}"/></linearGradient>'
                    '<radialGradient id="glow" cx=".82" cy=".1" r=".7">'
                    f'<stop offset="0" stop-color="{BRAND["p600"]}" stop-opacity=".45"/>'
                    f'<stop offset="1" stop-color="{BRAND["p600"]}" stop-opacity="0"/></radialGradient>'
                    '<radialGradient id="glow2" cx=".05" cy="1" r=".6">'
                    f'<stop offset="0" stop-color="{BRAND["orange"]}" stop-opacity=".08"/>'
                    f'<stop offset="1" stop-color="{BRAND["orange"]}" stop-opacity="0"/></radialGradient>'
                    f'<clipPath id="bc"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>')
    svg.add(f'<g clip-path="url(#bc)"><rect width="{w}" height="{h}" fill="url(#bb)"/>'
            f'<rect width="{w}" height="{h}" fill="url(#glow)"/><rect width="{w}" height="{h}" fill="url(#glow2)"/>')
    network_pattern(svg, w, h)
    svg.add("</g>")
    svg.add(f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{r}" fill="none" stroke="{BRAND["p600"]}" stroke-opacity=".45" stroke-width="2"/>')


def pill(svg, x, y, label, face="dm500", size=22, fg=None, bg=None, stroke=None, h=46, padx=22, anchor="start"):
    w = measure(label, face, size) + padx * 2
    if anchor == "middle":
        x -= w / 2
    svg.add(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{bg or "none"}"'
            + (f' stroke="{stroke}" stroke-width="2"' if stroke else "") + "/>")
    svg.text(x + w / 2, y + h / 2 + size * 0.36, label, face, size, fg, "middle")
    return w


# --------------------------------------------------------------------------- blocks
def hero():
    W, H = 1600, 600
    s = Svg(W, H, "WizOps — Infogérance Kubernetes & Cloud, de la conception à l'exploitation 24/7")
    brand_bg(s, W, H)
    s.logo(96, 104, 132)
    s.text(250, 158, "WizOps", "sora700", 52, BRAND["ink"])
    s.text(250, 198, "DEVOPS · SRE · IA — DEPUIS 15 ANS", "dm700", 19, BRAND["p400"], ls=3)
    s.text(96, 330, "Infogérance Kubernetes & Cloud", "sora700", 70, BRAND["ink"])
    s.text(96, 412, "De la conception à l'exploitation", "sora700", 70, BRAND["ink"])
    tw = measure("De la conception à l'exploitation ", "sora700", 70)
    s.text(96 + tw, 412, "24/7", "sora700", 70, BRAND["orange"])
    s.para(96, 474, "Startups, PME et secteur public : on construit votre infra 100 % en code, puis on l'opère. "
                    "Sans changement d'interlocuteur.", "dm400", 27, BRAND["muted"], 1100)
    x = 1600 - 96
    for label in ["Souveraineté & SecNumCloud", "Astreinte 24/7", "46 avis positifs sur Malt"][::-1]:
        w = measure(label, "dm500", 20) + 40
        x -= w
        pill(s, x, 92, label, "dm500", 20, BRAND["ink"], "#FFFFFF10", "#3FC1C955", h=42, padx=20)
        x -= 12
    s.render("hero.svg")


def button(name, label, primary):
    face, size = "sora600", 26
    w = int(measure(label, face, size) + 80 + 34)
    h = 76
    s = Svg(w, h, label)
    if primary:
        s.defs.append(f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FB8A3C"/>'
                      f'<stop offset="1" stop-color="#EA580C"/></linearGradient>')
        s.add(f'<rect width="{w}" height="{h}" rx="{h / 2}" fill="url(#bg)"/>')
        fg = "#FFFFFF"
    else:
        s.add(f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="{(h - 3) / 2}" fill="{BRAND["night"]}" '
              f'stroke="{BRAND["p400"]}" stroke-width="3"/>')
        fg = BRAND["ink"]
    s.text(40, h / 2 + size * 0.36, label, face, size, fg)
    s.icon("lu", "arrow-right", w - 40 - 26, h / 2 - 13, 26, fg, stroke=2.5)
    s.render(name)


def stats(theme):
    t = THEMES[theme]
    W, H = 1600, 250
    s = Svg(W, H, "Chiffres clés : 24/7, 100+ projets, 15+ ans, 46 avis Malt, 100 % de satisfaction")
    card_bg(s, t, 0, 0, W, H)
    items = [("24/7", "Support & monitoring", "365 jours par an"),
             ("100+", "Projets livrés", "Startups, PME, grands groupes"),
             ("15+ ans", "D'ingénierie", "Cloud, DevOps & SRE"),
             ("46", "Avis clients sur Malt", "100 % de satisfaction")]
    cw = W / 4
    for i, (n, l1, l2) in enumerate(items):
        cx = cw * i + cw / 2
        if i:
            s.add(f'<line x1="{cw * i}" y1="60" x2="{cw * i}" y2="{H - 60}" stroke="{t["border"]}" stroke-width="2"/>')
        s.text(cx, 118, n, "sora700", 64, t["accent"], "middle")
        s.text(cx, 164, l1, "dm700", 25, t["text"], "middle")
        s.text(cx, 198, l2, "dm400", 21, t["muted"], "middle")
    s.render(f"stats-{theme}.svg")


def featured(theme):
    t = THEMES[theme]
    W, H = 1600, 470
    s = Svg(W, H, "Infogérance 24/7 : votre infra conçue, puis opérée par la même équipe")
    card_bg(s, t, 0, 0, W, H, featured=True)
    s.add(f'<rect x="64" y="64" width="210" height="40" rx="20" fill="{t["accent"]}1F"/>')
    s.text(169, 91, "OFFRE PHARE", "dm700", 18, t["accent"], "middle", ls=2.5)
    icon_tile(s, t, "lu", "headset", 64, 136, 96)
    s.text(190, 182, "Infogérance 24/7", "sora700", 50, t["text"])
    s.text(190, 222, "Votre infra conçue, puis opérée par la même équipe.", "dm500", 26, t["muted"])
    s.para(64, 290, "Build ou reprise 100 % en code, supervision et astreinte, mises à jour, sécurité "
                    "et optimisation des coûts : un seul interlocuteur, du premier commit au run.",
           "dm400", 24, t["muted"], 720)
    bullets = ["Supervision & astreinte 24/7", "Sécurité, hardening & conformité",
               "FinOps : rightsizing et coûts maîtrisés", "AWS, Azure, GCP, Scaleway, OVH ou on-premise"]
    for i, b in enumerate(bullets):
        y = 150 + i * 62
        s.add(f'<circle cx="{900 + 20}" cy="{y + 20}" r="20" fill="{t["tint"]}"/>')
        s.icon("lu", "check", 908, y + 8, 24, t["petrol"], stroke=2.6)
        s.text(960, y + 29, b, "dm500", 26, t["text"])
    s.text(64, H - 44, "Découvrir l'offre", "dm700", 23, t["accent"])
    s.icon("lu", "arrow-right", 64 + measure("Découvrir l'offre ", "dm700", 23), H - 64, 26, t["accent"], 2.4)
    s.render(f"svc-infogerance-{theme}.svg")


SERVICES = [
    ("kubernetes", "si", "kubernetes", "Kubernetes & conteneurs", "Des clusters qui tiennent la charge",
     "EKS, AKS, GKE, Kapsule ou on-premise, en GitOps avec Helm et Argo CD. Zéro surprise en production."),
    ("migration", "lu", "arrow-right-left", "Migration Cloud", "Changer de cloud sans couper",
     "Vers le Cloud ou entre providers : une bascule planifiée, testée, avec un minimum d'interruption."),
    ("iac", "lu", "code-xml", "Infrastructure as Code", "Une infra 100 % en code",
     "Terraform, Ansible et CI/CD : reproductible, versionnée et revue. Fini la configuration à la main."),
    ("observabilite", "lu", "activity", "Observabilité", "Voir les incidents avant vos clients",
     "Grafana, Prometheus, Loki et Tempo : dashboards sur mesure et alerting proactif."),
    ("audit", "lu", "search-check", "Audit d'infrastructure", "Savoir exactement où vous en êtes",
     "Architecture, sécurité, performance et coûts : un rapport clair et des priorités concrètes."),
    ("aiops", "lu", "bot", "DevOps & IA (AIOps)", "L'IA qui investigue vos alertes",
     "Des agents IA analysent vos alertes de production et proposent la cause racine."),
]


def service(theme, key, kind, icon, name, punch, desc):
    t = THEMES[theme]
    W, H = 784, 340
    s = Svg(W, H, f"{name} — {punch}")
    card_bg(s, t, 0, 0, W, H)
    icon_tile(s, t, kind, icon, 48, 48, 80)
    s.text(152, 82, name.upper(), "dm700", 19, t["petrol"], ls=2)
    s.text(152, 120, punch, "sora700", 31, t["text"])
    s.para(48, 186, desc, "dm400", 24, t["muted"], W - 96)
    s.text(48, H - 40, "En savoir plus", "dm700", 21, t["accent"])
    s.icon("lu", "arrow-right", 48 + measure("En savoir plus ", "dm700", 21), H - 58, 22, t["accent"], 2.4)
    s.render(f"svc-{key}-{theme}.svg")


def method(theme):
    t = THEMES[theme]
    W, H = 1600, 330
    s = Svg(W, H, "Notre méthode : Audit, Build, Run 24/7, Amélioration continue")
    card_bg(s, t, 0, 0, W, H)
    steps = [("scan-search", "Audit", "On cartographie l'existant", "et les priorités."),
             ("hammer", "Build", "On construit ou reprend", "votre infra en code."),
             ("headset", "Run 24/7", "On opère, on supervise,", "on assure l'astreinte."),
             ("refresh-ccw", "Amélioration", "On optimise fiabilité", "et coûts, en continu.")]
    cw = (W - 128) / 4
    y0 = 108
    s.add(f'<line x1="{64 + cw / 2}" y1="{y0}" x2="{64 + cw * 3.5}" y2="{y0}" stroke="{t["border"]}" '
          f'stroke-width="3" stroke-dasharray="2 12" stroke-linecap="round"/>')
    for i, (ic, name, l1, l2) in enumerate(steps):
        cx = 64 + cw * i + cw / 2
        s.add(f'<circle cx="{cx}" cy="{y0}" r="46" fill="{t["card"]}" stroke="{t["petrol2"]}" stroke-width="2.5"/>')
        s.icon("lu", ic, cx - 20, y0 - 20, 40, t["petrol"], 1.9)
        s.add(f'<circle cx="{cx + 36}" cy="{y0 - 36}" r="17" fill="{t["accent"]}"/>')
        s.text(cx + 36, y0 - 29, str(i + 1), "dm700", 19, "#FFFFFF", "middle")
        s.text(cx, 202, name, "sora700", 32, t["text"], "middle")
        s.text(cx, 242, l1, "dm400", 22, t["muted"], "middle")
        s.text(cx, 272, l2, "dm400", 22, t["muted"], "middle")
    s.render(f"method-{theme}.svg")


STACK = [("Orchestration", [("kubernetes", "Kubernetes"), ("helm", "Helm"), ("argo", "Argo CD"), ("docker", "Docker")]),
         ("Cloud", [("amazonwebservices", "AWS"), ("microsoftazure", "Azure"), ("googlecloud", "GCP"),
                    ("scaleway", "Scaleway"), ("ovh", "OVHcloud")]),
         ("IaC & CI/CD", [("terraform", "Terraform"), ("ansible", "Ansible"), ("githubactions", "Actions"),
                          ("gitlab", "GitLab CI")]),
         ("Observabilité", [("grafana", "Grafana"), ("prometheus", "Prometheus")])]


def stack(theme):
    t = THEMES[theme]
    W, H = 1600, 560
    s = Svg(W, H, "Notre stack : Kubernetes, Helm, Argo CD, Docker, AWS, Azure, GCP, Scaleway, OVHcloud, "
                  "Terraform, Ansible, GitHub Actions, GitLab CI, Grafana, Prometheus")
    card_bg(s, t, 0, 0, W, H)
    gap, m = 26, 56
    gw, gh = (W - 2 * m - gap) / 2, (H - 2 * m - gap) / 2
    for k, (title, items) in enumerate(STACK):
        x, y = m + (k % 2) * (gw + gap), m + (k // 2) * (gh + gap)
        s.add(f'<rect x="{x}" y="{y}" width="{gw}" height="{gh}" rx="22" fill="{t["soft"]}" stroke="{t["border"]}" stroke-width="1.5"/>')
        s.text(x + 32, y + 50, title.upper(), "dm700", 19, t["petrol"], ls=2.5)
        slot = (gw - 40) / 5
        x0 = x + (gw - slot * len(items)) / 2
        for j, (ic, label) in enumerate(items):
            cx = x0 + slot * j + slot / 2
            s.icon("si", ic, cx - 32, y + 86, 64, t["text"])
            s.text(cx, y + 194, label, "dm500", 22, t["muted"], "middle")
    s.render(f"stack-{theme}.svg")


def product(theme, key, kind, icon, name, tag, desc, cta):
    t = THEMES[theme]
    W, H = 784, 320
    s = Svg(W, H, f"{name} — {tag}")
    card_bg(s, t, 0, 0, W, H)
    icon_tile(s, t, kind, icon, 48, 48, 80)
    s.text(152, 92, name, "sora700", 38, t["text"])
    s.text(152, 126, tag, "dm500", 22, t["petrol"])
    s.para(48, 192, desc, "dm400", 24, t["muted"], W - 96)
    s.text(48, H - 40, cta, "dm700", 21, t["accent"])
    s.icon("lu", "arrow-right", 48 + measure(cta + " ", "dm700", 21), H - 58, 22, t["accent"], 2.4)
    s.render(f"prod-{key}-{theme}.svg")


def oss(theme):
    t = THEMES[theme]
    W, H = 1600, 230
    s = Svg(W, H, "Open source : prometheus-ovh-exporter, un exporter Prometheus pour OVHcloud")
    card_bg(s, t, 0, 0, W, H)
    icon_tile(s, t, "si", "prometheus", 56, 56, 92)
    s.text(180, 92, "OPEN SOURCE · GO · APACHE 2.0", "dm700", 18, t["petrol"], ls=2)
    s.text(180, 136, "prometheus-ovh-exporter", "sora700", 38, t["text"])
    s.text(180, 180, "Facturation, consommation, quotas, instances, stockage et savings plans OVHcloud,"
                     " prêts pour Grafana et votre suivi FinOps.", "dm400", 23, t["muted"])
    s.render(f"oss-ovh-exporter-{theme}.svg")


TESTIMONIALS = [
    ("didask", "Arnaud", "CTO · Didask",
     "Merci à Julien pour tout son accompagnement qui nous a permis de déployer notre solution SaaS "
     "dans deux contextes particuliers (on premise et SecNumCloud). Agit rapidement et efficacement […], "
     "le résultat est documenté."),
    ("toha", "Gabriel", "CTO · Toha",
     "Il a su apporter son expertise devops à l'équipe […]. Il est un expert dévoué, curieux, "
     "pragmatique qui saura apporter des solutions simples à des problèmes complexes."),
]


def testimonial(theme, key, name, role, quote):
    t = THEMES[theme]
    W, H = 784, 400
    s = Svg(W, H, f"Avis de {name}, {role}")
    card_bg(s, t, 0, 0, W, H)
    s.icon("lu", "quote", 48, 44, 52, t["petrol"], 1.6)
    for i in range(5):
        s.icon("lu", "star", W - 48 - 32 * (5 - i), 54, 26, t["star"], 2)
        s.parts[-1] = s.parts[-1].replace('fill="none"', f'fill="{t["star"]}"')
    s.para(48, 150, quote, "dm400", 25, t["text"], W - 96, lh=1.5)
    s.add(f'<circle cx="80" cy="{H - 64}" r="32" fill="{t["tint"]}"/>')
    s.text(80, H - 54, name[0], "sora700", 28, t["petrol"], "middle")
    s.text(128, H - 70, name, "dm700", 23, t["text"])
    s.text(128, H - 40, role, "dm400", 20, t["muted"])
    s.render(f"quote-{key}-{theme}.svg")


def clients(theme):
    t = THEMES[theme]
    W, H = 1600, 180
    names = ["Caast.TV", "Didask", "Epiconcept", "Toha", "F2R2", "Okeiro", "UserAdgents", "Tekyn",
             "Process Metronome", "Greenmetrics", "Keepen"]
    s = Svg(W, H, "Ils nous font confiance : " + ", ".join(names))
    card_bg(s, t, 0, 0, W, H)
    rows = [names[:6], names[6:]]
    for r, row in enumerate(rows):
        widths = [measure(n, "sora600", 30) for n in row]
        sep = 70
        total = sum(widths) + sep * (len(row) - 1)
        x = (W - total) / 2
        y = 78 + r * 56
        for i, (n, w) in enumerate(zip(row, widths)):
            s.text(x, y, n, "sora600", 30, t["muted"])
            if i < len(row) - 1:
                s.add(f'<circle cx="{x + w + sep / 2}" cy="{y - 10}" r="4" fill="{t["accent"]}"/>')
            x += w + sep
    s.render(f"clients-{theme}.svg")


def cta():
    W, H = 1600, 380
    s = Svg(W, H, "Un projet Kubernetes, une migration ou besoin d'astreinte ? Réservez 30 minutes avec Julien")
    brand_bg(s, W, H)
    s.text(W / 2, 128, "Un projet Kubernetes, une migration,", "sora700", 50, BRAND["ink"], "middle")
    s.text(W / 2, 192, "besoin d'astreinte ?", "sora700", 50, BRAND["ink"], "middle")
    s.text(W / 2, 244, "30 minutes pour en parler, sans engagement.", "dm400", 27, BRAND["muted"], "middle")
    label = "Réserver un créneau avec Julien"
    w = measure(label, "sora600", 27) + 120
    x = (W - w) / 2
    s.defs.append('<linearGradient id="cb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FB8A3C"/>'
                  '<stop offset="1" stop-color="#EA580C"/></linearGradient>')
    s.add(f'<rect x="{x}" y="278" width="{w}" height="70" rx="35" fill="url(#cb)"/>')
    s.icon("lu", "calendar-days", x + 36, 299, 28, "#FFFFFF", 2.2)
    s.text(x + 78, 322, label, "sora600", 27, "#FFFFFF")
    s.render("cta.svg")


hero()
cta()
button("btn-rdv.svg", "Réserver un audit", True)
button("btn-site.svg", "wizops.fr", False)
for th in THEMES:
    stats(th)
    featured(th)
    for svc in SERVICES:
        service(th, *svc)
    method(th)
    stack(th)
    product(th, "wizstatus", "lu", "activity", "WizStatus", "Monitoring & pages de statut",
            "Surveillez vos sites, API et services avec des alertes en temps réel et de belles pages de statut.",
            "wizstatus.com")
    product(th, "mongoadmin", "si", "mongodb", "MongoAdmin", "Client MongoDB desktop",
            "Natif, écrit en Rust, sans Electron. Requêtes, agrégations et monitoring, avec une offre gratuite.",
            "mongoadmin.dev")
    oss(th)
    for q in TESTIMONIALS:
        testimonial(th, *q)
    clients(th)
