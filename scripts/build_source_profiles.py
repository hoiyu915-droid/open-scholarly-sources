#!/usr/bin/env python3
"""Generate source-use tiers, archetypes and 0–4 routing heuristics."""

from __future__ import annotations
import argparse, html, json
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
BASE="https://hoiyu915-droid.github.io/open-scholarly-sources"
SCORES=("academic_rigor","frontier_velocity","signal_density","machine_readability","version_clarity","oa_reliability","specialization","noise_risk")
REPOS={"institutional_repository","subject_repository","government_repository","digital_library"}
DISC={"directory","aggregator"}
METHODS={"methods","scientific software","data science","instrumentation","computational modeling","bioinformatics"}
CLINICAL={"clinical medicine","medicine","public health","global health","health policy","molecular medicine"}
POLICY={"economics","economic theory","political science","law","legal studies","public health","health policy","demography","population studies"}

def load(p): return json.loads(p.read_text(encoding="utf-8"))
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def clamp(x): return max(0,min(4,int(x)))

def sources():
    m=load(DATA/"registry-manifest.json"); out=[]
    for f in m["source_shards"]: out+=load(DATA/f)["sources"]
    out.sort(key=lambda x:(x["name"].casefold(),x["id"]))
    return m,out

def score(s):
    peer,pub,typ=s["peer_review_scope"],s["publication_state"],s["source_type"]
    subs=set(s.get("subjects") or [])
    spec=1 if {"multidisciplinary","interdisciplinary science"}&subs else 4 if len(subs)<=2 else 3 if len(subs)<=4 else 2 if len(subs)<=8 else 1
    rigor=4 if peer=="peer_reviewed" and pub=="published" else 3 if peer=="peer_reviewed" else 2 if peer=="mixed" or pub=="mixed" else 1 if peer=="not_peer_reviewed" and pub=="preprint" else 0
    pol=s.get("access_policy") or {}; vers=set(pol.get("version_scope") or [])
    velocity=4 if pub=="preprint" or typ=="review_platform" else 3 if {"preprint","accepted_manuscript"}&vers else 2 if typ in {"journal","proceedings_series"} else 1 if typ in REPOS|DISC else 2
    signal=4 if peer=="peer_reviewed" and pub=="published" else 3 if peer=="peer_reviewed" else (3 if spec>=4 else 2) if peer=="mixed" or pub=="preprint" else 2
    ma=s.get("machine_access") or {}; eps=sum(bool(ma.get(k)) for k in ("feed_url","api_url","oai_pmh_url","bulk_metadata_url")); sf=len(set(ma.get("formats") or [])&{"xml","json","csv","rdf"})
    machine=4 if eps>=2 or (eps and sf) else 3 if eps==1 or sf else 2 if ma.get("formats") else 1
    roles=set(s.get("access_roles") or [])
    vclar=4 if pub=="published" and "canonical_vor" in roles else 3 if len(vers)==1 and "mixed" not in vers else 2 if len(vers)>1 or "mixed" in vers or pub=="preprint" else 1
    oa={"full":4,"mixed":2,"metadata_only":1,"unknown":0}.get(s["oa_scope"],0)
    noise=4 if peer=="not_peer_reviewed" and pub=="preprint" else 3 if peer=="mixed" or pub=="mixed" else 2 if typ in DISC or typ=="review_platform" else 1 if peer=="peer_reviewed" else 2
    return dict(zip(SCORES,map(clamp,(rigor,velocity,signal,machine,vclar,oa,spec,noise))))

def tier(s,sc):
    typ,pub=s["source_type"],s["publication_state"]
    if typ in DISC or typ=="review_platform": return "D1"
    if typ in REPOS and pub!="preprint": return "A1"
    if pub=="preprint":
        return "F1" if s["status"]=="active" and s["verification"]["status"]=="verified" and s.get("parent_id")!="osf-preprints" else "F2"
    roles=set(s.get("access_roles") or [])
    if pub=="published" and s["peer_review_scope"]=="peer_reviewed" and "canonical_vor" in roles: return "R1"
    if pub in {"published","mixed"} and s["peer_review_scope"] in {"peer_reviewed","mixed"}: return "R2"
    return "F2" if sc["frontier_velocity"]>=3 else "R2"

def archetypes(s,sc,t):
    a=set(); subs=set(s.get("subjects") or []); roles=set(s.get("access_roles") or []); pol=s.get("access_policy") or {}; vers=set(pol.get("version_scope") or [])
    nn=(s["name"]+" "+s.get("notes","")).casefold()
    if t=="R1": a.add("formal_anchor")
    if s["publication_state"]=="preprint": a.add("frontier_scout")
    if sc["specialization"]>=4: a.add("specialist_hunter")
    if sc["specialization"]<=1 and sc["frontier_velocity"]>=3: a.add("broad_firehose")
    if s["source_type"] in REPOS: a.add("archive_backbone")
    if s["source_type"] in DISC: a.add("discovery_infrastructure")
    if s["source_type"]=="review_platform": a.add("review_observatory")
    if len(vers)>1 or "mixed" in vers or {"repository_copy","canonical_vor"}<=roles: a.add("version_bridge")
    if subs&METHODS: a.add("methods_workshop")
    if s["publication_state"]=="preprint" and subs&CLINICAL: a.add("clinical_early_warning")
    if subs&POLICY and any(x in nn for x in ("working paper","discussion paper","policy","econom")): a.add("policy_signal")
    if s.get("parent_id")=="osf-preprints": a.add("community_hub")
    if {"multidisciplinary","interdisciplinary science"}&subs: a.add("cross_disciplinary_hub")
    if not a: a.add("formal_anchor" if sc["academic_rigor"]>=3 else "discovery_infrastructure")
    return sorted(a)

def confidence(s):
    v=s["verification"]["status"]
    return "high" if v=="verified" and s.get("access_policy") else "medium" if v in {"verified","partial"} else "low"

def validate_rules(r,ids):
    if set(r["dimensions"])!=set(SCORES): raise SystemExit("profile dimensions mismatch")
    if set(r["tiers"])!={"R1","R2","F1","F2","D1","A1"}: raise SystemExit("profile tiers incomplete")
    unknown=set(r.get("overrides",{}))-ids
    if unknown: raise SystemExit(f"unknown profile override IDs: {sorted(unknown)}")
    valid=set(r["archetypes"])
    for sid,o in r.get("overrides",{}).items():
        bad=(set(o.get("add_archetypes",[]))|set(o.get("remove_archetypes",[])))-valid
        if bad: raise SystemExit(f"{sid}: unknown archetypes {sorted(bad)}")

def make_profile(s,r,base):
    sc=score(s); t=tier(s,sc); a=set(archetypes(s,sc,t)); o=r.get("overrides",{}).get(s["id"],{})
    t=o.get("tier",t); a.update(o.get("add_archetypes",[])); a.difference_update(o.get("remove_archetypes",[])); a=sorted(a)
    labels=r["archetypes"]; top=a[:3]
    return {"source_id":s["id"],"tier":t,"archetypes":a,"scores":sc,"confidence":confidence(s),"method":r["method"],
      "character":{"en":" · ".join(labels[x]["en"] for x in top),"zh-TW":" · ".join(labels[x]["zh-TW"] for x in top)},
      "profile_url":f"{base}/profiles/#{quote(s['id'])}",
      "disclaimer":{"en":"Source-level use profile only; not a ranking of article quality, prestige, validity, or truth.","zh-TW":"僅為來源層級的使用剖面；不是單篇文章品質、聲望、有效性或真偽排名。"}}

def page(ps,sm,r):
    trs=[]
    for p in ps:
        s=sm[p["source_id"]]; arches=" ".join(f'<span>{html.escape(r["archetypes"][a]["en"])} / {html.escape(r["archetypes"][a]["zh-TW"])}</span>' for a in p["archetypes"])
        scores=" · ".join(f'{k.replace("_"," ")} {v}/4' for k,v in p["scores"].items())
        trs.append(f'<tr id="{p["source_id"]}" data-tier="{p["tier"]}" data-arch="{" ".join(p["archetypes"])}"><td><a href="../sources/{p["source_id"]}.html"><b>{html.escape(s["name"])}</b></a><br><code>{p["source_id"]}</code></td><td><b>{p["tier"]}</b><br>{html.escape(r["tiers"][p["tier"]]["en"])} / {html.escape(r["tiers"][p["tier"]]["zh-TW"])}</td><td>{arches}<br><small>{html.escape(p["character"]["zh-TW"])}</small></td><td><small>{html.escape(scores)}</small></td><td>{p["confidence"]}</td></tr>')
    topts="".join(f'<option value="{k}">{k} · {v["en"]} / {v["zh-TW"]}</option>' for k,v in r["tiers"].items())
    aopts="".join(f'<option value="{k}">{v["en"]} / {v["zh-TW"]}</option>' for k,v in r["archetypes"].items())
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Source profiles｜來源性格</title>
<style>:root{{color-scheme:light dark}}body{{font:15px/1.55 system-ui,"Noto Sans TC",sans-serif;max-width:1500px;margin:40px auto;padding:0 18px}}a{{color:inherit}}.note{{padding:12px;border:1px solid #8886;border-radius:12px}}.ctl{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:8px;margin:18px 0}}input,select{{padding:9px}}.wrap{{overflow:auto;border:1px solid #8886;border-radius:12px}}table{{border-collapse:collapse;width:100%;min-width:1100px}}th,td{{padding:11px;border-bottom:1px solid #8885;vertical-align:top;text-align:left}}span{{display:inline-block;border:1px solid #8886;border-radius:999px;padding:2px 6px;margin:2px;font-size:11px}}small,code{{opacity:.75}}@media(max-width:700px){{.ctl{{grid-template-columns:1fr}}}}</style></head><body>
<p><a href="../">← Open Scholarly Sources / 開放學術來源</a></p><h1>Source-use profiles｜來源分級與性格</h1>
<p>Six routing tiers, named archetypes and eight ordinal 0–4 dimensions. These describe how to use a source; they are not prestige or article-quality rankings.</p>
<p>六種用途 tier、來源 archetype 與八個 0–4 序位軸。它們描述「這個來源怎麼用」，不是期刊聲望或單篇文章品質排名。</p>
<div class="note"><b>Important / 重要：</b> high <code>noise_risk</code> means more filtering is needed, not that the source is bad. 前沿來源可以同時是 F1 與高 noise risk。</div>
<div class="ctl"><input id="q" type="search" placeholder="Search / 搜尋"><select id="t"><option value="">All tiers / 全部 tier</option>{topts}</select><select id="a"><option value="">All archetypes / 全部性格</option>{aopts}</select></div><p id="n">{len(ps)} profiles</p>
<div class="wrap"><table><thead><tr><th>Source</th><th>Tier</th><th>Archetypes / 性格</th><th>Scores / 八軸</th><th>Confidence</th></tr></thead><tbody id="rows">{''.join(trs)}</tbody></table></div>
<script>const q=document.querySelector("#q"),t=document.querySelector("#t"),a=document.querySelector("#a"),rs=[...document.querySelectorAll("#rows tr")],n=document.querySelector("#n");function f(){{let c=0,s=q.value.toLowerCase(),tv=t.value,av=a.value;for(const r of rs){{let ok=(!s||r.textContent.toLowerCase().includes(s))&&(!tv||r.dataset.tier===tv)&&(!av||r.dataset.arch.split(" ").includes(av));r.hidden=!ok;if(ok)c++}}n.textContent=c+" / "+rs.length+" profiles"}}q.oninput=f;t.onchange=f;a.onchange=f;</script></body></html>"""

def enrich(output,ps,pm,base):
    rp=output/"registry.json"
    if rp.exists():
        reg=load(rp)
        for x in reg["sources"]: x["source_profile"]=pm[x["id"]]
        dump(rp,reg); (output/"registry.ndjson").write_text("".join(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n" for x in reg["sources"]),encoding="utf-8")
    lp=output/"llms.txt"
    if lp.exists():
        x=lp.read_text(encoding="utf-8")
        if "## Source-use profiles / 來源分級與性格" not in x:
            x+=f'\n## Source-use profiles / 來源分級與性格\n- [Profiles JSON]({base}/source-profiles.json)\n- [Profiles NDJSON]({base}/source-profiles.ndjson)\n- [Browsable profiles]({base}/profiles/)\n- Profiles are routing heuristics, not prestige or article-quality rankings; high `noise_risk` means more filtering.\n'
            lp.write_text(x,encoding="utf-8")
    fp=output/"llms-full.txt"
    if fp.exists():
        x=fp.read_text(encoding="utf-8")
        lines=["","## Source-use profiles — routing layer","","0–4 ordinal source-use heuristics; not prestige, validity or truth rankings.",""]
        for p in ps:
            lines+= [f'### {p["source_id"]} — {p["tier"]}',f'- Character: {p["character"]["en"]} / {p["character"]["zh-TW"]}',f'- Archetypes: {", ".join(p["archetypes"])}','- Scores: '+", ".join(f"{k}={v}/4" for k,v in p["scores"].items()),f'- Confidence: {p["confidence"]}',f'- Profile: {p["profile_url"]}',""]
        if "## Source-use profiles — routing layer" not in x: fp.write_text(x.rstrip()+"\n"+"\n".join(lines),encoding="utf-8")
    ip=output/"index.html"
    if ip.exists():
        x=ip.read_text(encoding="utf-8"); m='<a href="./llms-full.txt">LLM full index / 完整索引</a>'
        if m in x and "Source profiles / 來源性格" not in x: x=x.replace(m,m+'\n      <a href="./profiles/">Source profiles / 來源性格</a>',1)
        ip.write_text(x,encoding="utf-8")
    sp=output/"sitemap.xml"
    if sp.exists():
        x=sp.read_text(encoding="utf-8"); u=base+"/profiles/"
        if u not in x: x=x.replace("</urlset>",f"  <url><loc>{u}</loc></url>\n</urlset>")
        sp.write_text(x,encoding="utf-8")

def build(output,base):
    m,ss=sources(); r=load(DATA/"source-profile-rules.json"); ids={s["id"] for s in ss}; validate_rules(r,ids)
    ps=[make_profile(s,r,base) for s in ss]
    if len(ps)!=len(ids) or len({p["source_id"] for p in ps})!=len(ps): raise SystemExit("profile coverage/uniqueness failure")
    output.mkdir(parents=True,exist_ok=True); (output/"profiles").mkdir(exist_ok=True)
    sm={s["id"]:s for s in ss}; pm={p["source_id"]:p for p in ps}
    payload={"schema_version":r["schema_version"],"updated":m["updated"],"method":r["method"],"scale":{"min":0,"max":4},"profiles":ps}
    dump(output/"source-profiles.json",payload); (output/"source-profiles.ndjson").write_text("".join(json.dumps(p,ensure_ascii=False,separators=(",",":"))+"\n" for p in ps),encoding="utf-8")
    (output/"profiles"/"index.html").write_text(page(ps,sm,r),encoding="utf-8"); enrich(output,ps,pm,base)
    c={k:0 for k in r["tiers"]}
    for p in ps:c[p["tier"]]+=1
    print("Source profiles OK:",len(ps),"profiles;",", ".join(f"{k}={c[k]}" for k in ("R1","R2","F1","F2","D1","A1")))

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--base-url",default=BASE);a=p.parse_args();build(a.output,a.base_url.rstrip("/"))
if __name__=="__main__": main()
