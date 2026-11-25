"""Génère une page HTML statique par club (club/*.html), une page par département
(clubs/*.html), sitemap.xml et robots.txt à partir de index.html.
Usage : python3 tools/build_seo.py   (nécessite playwright + chromium)"""
import asyncio, json, os, re, shutil, html, http.server, threading, functools
from playwright.async_api import async_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://volleyspot.fr/'
DUMP = """window.__VS_DUMP = () => clubs.map(c => ({ id: rawClubId(c), slug: clubSlug(c), name: c.name, city: c.city,
  postcode: c.postcode, dep: c.dep, depLabel: depLabel(c.dep), gender: c.gender, cats: pouleLabels(c.categories),
  lat: c.latitude, lon: c.longitude, approx: !!c.geo_approx, colors: c.couleurs || '',
  gyms: (c.gymsList || []).map(g => ({ name: g.name, address: g.address, postcode: g.postcode, city: g.city })) }));
"""
def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory='/tmp/vs_seo')
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8799), h); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv
async def dump():
    shutil.rmtree('/tmp/vs_seo', ignore_errors=True); shutil.copytree(ROOT, '/tmp/vs_seo', ignore=shutil.ignore_patterns('.git', 'club', 'clubs'))
    p = '/tmp/vs_seo/index.html'; s = open(p, encoding='utf-8').read()
    i = s.rindex('})();\n</script>'); s = s[:i] + DUMP + s[i:]; open(p, 'w', encoding='utf-8').write(s)
    srv = serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path=os.environ.get('CHROME', '/usr/bin/google-chrome'), args=['--no-sandbox'])
        pg = await b.new_page()
        async def route(r):
            await (r.continue_() if r.request.url.startswith('http://127.0.0.1:8799') else r.abort())
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8799/index.html'); await pg.wait_for_timeout(3000)
        data = await pg.evaluate('window.__VS_DUMP()'); await b.close()
    srv.shutdown(); return data
E = lambda x: html.escape(str(x or ''))
CSS = """body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f1e7;color:#1d2a2b;line-height:1.5}
main{max-width:720px;margin:0 auto;padding:24px 18px 60px}a{color:#0f6b62}header a{font-weight:800;text-decoration:none;color:#1d2a2b;font-size:20px}
header span{color:#e04e39}h1{font-size:26px;margin:18px 0 4px}.sub{color:#5b6b6c;margin:0 0 16px}.card{background:#fff;border:1px solid #e6dccb;border-radius:14px;padding:14px 16px;margin:14px 0}
.pill{display:inline-block;background:#f6f1e7;border:1px solid #e6dccb;border-radius:8px;padding:2px 9px;margin:2px 4px 2px 0;font-size:13px;font-weight:600}
.cta{display:inline-block;background:#e04e39;color:#fff;border-radius:12px;padding:12px 18px;font-weight:700;text-decoration:none;margin-top:8px}
ul{padding-left:18px}li{margin:4px 0}footer{color:#7b8a8b;font-size:12.5px;margin-top:30px}"""
def page(title, desc, canon, body, ld=None):
    ld_tag = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' if ld else ''
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{canon}"><meta property="og:type" content="website">
<link rel="icon" href="../icons/icon-192.png"><style>{CSS}</style>{ld_tag}</head><body><main>
<header><a href="../">Volley<span>Spot</span></a></header>{body}
<footer>Données issues de l'annuaire public de la FFVolley. VolleySpot est un projet indépendant, non affilié à la FFVolley.</footer></main></body></html>"""
SMALL = {'de','du','des','la','le','les','sur','sous','en','et','aux','au','lès','les'}
def tcity(x):
    x = (x or '').strip()
    if not x or x != x.upper(): return x
    def w(i, t): return t if (i and t in SMALL) else '-'.join(p[:1].upper() + p[1:] for p in t.split('-'))
    out = ' '.join(w(i, t) for i, t in enumerate(x.lower().split()))
    return re.sub(r"\b([DL])'(\w)", lambda m: m.group(1).lower() + "'" + m.group(2).upper(), out).replace('St ', 'St-').replace('Ste ', 'Ste-')
def dslug(dep): return re.sub(r'[^a-z0-9]+', '-', dep.lower())
def build(data):
    for d in ('club', 'clubs'): shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True); os.makedirs(os.path.join(ROOT, d))
    urls = []
    bydep = {}
    for c in data:
        c['city'] = tcity(c['city'])
        for g in c['gyms']: g['city'] = tcity(g.get('city'))
        bydep.setdefault(c['dep'] or '', []).append(c)
        cats = ''.join(f'<span class="pill">{E(x)}</span>' for x in (c['cats'] or [])) or '<span class="pill">Catégories non renseignées</span>'
        gyms = ''.join(f"<li><b>{E(g['name'])}</b> — {E(', '.join(x for x in [g.get('address'), ' '.join(x for x in [g.get('postcode'), g.get('city')] if x)] if x))}</li>" for g in c['gyms'])
        app = f"../?club={c['id']}"
        dep_link = f'<a href="../clubs/{dslug(c["dep"])}.html">{E(c["depLabel"])}</a>' if c['dep'] else ''
        title = f"{c['name']} — club de volley à {c['city']}"
        desc = f"{c['name']}, club de volley-ball affilié FFVolley à {c['city']}" + (f" ({c['postcode']})" if c['postcode'] else '') + ". Salles, catégories, contact et itinéraire sur VolleySpot."
        body = f"""<h1>{E(c['name'])}</h1><p class="sub">Club de volley-ball à {E(c['city'])}{(' (' + E(c['postcode']) + ')') if c['postcode'] else ''}{(' · ' + dep_link) if dep_link else ''}</p>
<div class="card"><b>Catégories et championnats</b><br>{cats}<br><span class="pill">{E(c['gender'])}</span>{('<span class="pill">Couleurs : ' + E(c['colors']) + '</span>') if c['colors'] else ''}</div>
<div class="card"><b>Où jouer</b>{('<ul>' + gyms + '</ul>') if gyms else '<p>Salle non renseignée par la fédération.</p>'}</div>
<a class="cta" href="{app}">Voir sur la carte et contacter le club</a>"""
        canon = BASE + 'club/' + c['slug'] + '.html'
        ld = {"@context": "https://schema.org", "@type": "SportsOrganization", "name": c['name'], "sport": "Volleyball", "url": canon,
              "address": {"@type": "PostalAddress", "addressLocality": c['city'], "postalCode": c['postcode'] or None, "addressCountry": "FR"}}
        if c['lat'] is not None and not c['approx']: ld["geo"] = {"@type": "GeoCoordinates", "latitude": c['lat'], "longitude": c['lon']}
        open(os.path.join(ROOT, 'club', c['slug'] + '.html'), 'w', encoding='utf-8').write(page(title, desc, canon, body, ld)); urls.append(canon)
    deps = sorted(bydep.items(), key=lambda kv: kv[0])
    for dep, cl in deps:
        if not dep: continue
        lbl = cl[0]['depLabel']; name = lbl.split('·', 1)[-1].strip()
        items = ''.join(f'<li><a href="../club/{c["slug"]}.html">{E(c["name"])}</a> — {E(c["city"])}</li>' for c in sorted(cl, key=lambda c: (c['city'], c['name'])))
        canon = BASE + 'clubs/' + dslug(dep) + '.html'
        body = f'<h1>Clubs de volley — {E(name)}</h1><p class="sub">{len(cl)} clubs affiliés FFVolley</p><div class="card"><ul>{items}</ul></div><a class="cta" href="../">Ouvrir la carte</a>'
        open(os.path.join(ROOT, 'clubs', dslug(dep) + '.html'), 'w', encoding='utf-8').write(page(f'Clubs de volley — {name} ({dep})', f'Les {len(cl)} clubs de volley-ball affiliés FFVolley en {name} : salles, catégories, contact.', canon, body)); urls.append(canon)
    idx = ''.join(f'<li><a href="{dslug(d)}.html">{E(cl[0]["depLabel"])}</a> ({len(cl)})</li>' for d, cl in deps if d)
    open(os.path.join(ROOT, 'clubs', 'index.html'), 'w', encoding='utf-8').write(page('Tous les clubs de volley en France par département', f'{len(data)} clubs de volley-ball affiliés FFVolley, classés par département.', BASE + 'clubs/', f'<h1>Clubs de volley par département</h1><p class="sub">{len(data)} clubs</p><div class="card"><ul>{idx}</ul></div>'))
    urls = [BASE, BASE + 'clubs/'] + urls
    open(os.path.join(ROOT, 'sitemap.xml'), 'w').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'<url><loc>{u}</loc></url>\n' for u in urls) + '</urlset>\n')
    open(os.path.join(ROOT, 'robots.txt'), 'w').write(f'User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n')
    print(len(data), 'clubs,', len(urls), 'URLs')
if __name__ == '__main__':
    build(asyncio.run(dump()))
