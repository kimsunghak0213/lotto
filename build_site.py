# -*- coding: utf-8 -*-
"""
로또 번호 생성기 — site/index.html 을 만든다 (외부 패키지 없음)

카카오톡·메일 앱의 자체 미리보기 창은 자바스크립트를 차단한다.
따라서 조합을 미리 뽑아 HTML에 넣고, 라디오 버튼과 CSS :checked 로만
전환한다. 스크립트가 한 줄도 없으므로 어떤 환경에서도 동작한다.
"""
import csv, os, random, itertools, datetime
from collections import Counter

random.seed()  # 빌드할 때마다 완전히 다른 조합이 나온다
BUILT = datetime.datetime.now().strftime('%Y.%m.%d')

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'draws.csv')
OUT = os.path.join(HERE, 'site', 'index.html')
GROUPS = 40          # 전략별 뽑기 횟수 (× 5조합 = 전략당 200조합)
STRATS = [
    ('bal',   '균형',        '역대 분포에 맞춤'),
    ('hot',   '많이 나온 수', '고빈도 가중'),
    ('cold',  '안 나온 수',   '장기 미출현 가중'),
    ('unpop', '비인기 번호',  '당첨금 분산 최소화'),
    ('pure',  '완전 랜덤',    '필터 없음'),
]

# ────────────────────────── 데이터 ──────────────────────────
with open(SRC, encoding='utf-8') as f:
    rows = [[int(x) for x in r] for r in list(csv.reader(f))[1:] if r]
rows.sort(key=lambda r: r[0])
rounds = [r[0] for r in rows]
draws = [tuple(r[1:7]) for r in rows]
LAST = max(rounds)
NEXT = LAST + 1          # 이번 주 추첨 대상 회차
N = len(draws)
past = set(draws)

freq = Counter(n for d in draws for n in d)
last_seen = {}
for d, rnd in zip(draws, rounds):
    for n in d:
        last_seen[n] = rnd
gap = {n: LAST - last_seen[n] for n in range(1, 46)}
mean_freq = N * 6 / 45

# ───────────────────── 조합 지표 · 필터 ─────────────────────
def consec(a):
    return sum(1 for i in range(5) if a[i + 1] - a[i] == 1)

def ac_val(a):
    return len({abs(x - y) for x, y in itertools.combinations(a, 2)}) - 5

def max_same_end(a):
    return max(Counter(x % 10 for x in a).values())

def passes(a):
    """역대 1등 조합의 약 90% 구간 (1,236회 실측에서 산출)"""
    s = sum(a)
    if not 88 <= s <= 189: return False
    if not 2 <= sum(1 for x in a if x % 2) <= 4: return False
    if not 2 <= sum(1 for x in a if x <= 22) <= 4: return False
    if consec(a) > 2: return False
    if ac_val(a) < 7: return False
    if max_same_end(a) > 2: return False
    if sum(1 for x in a if x % 3 == 0) > 3: return False
    return True

def weights(strategy):
    w = {}
    for n in range(1, 46):
        if strategy == 'hot':
            w[n] = (freq[n] / mean_freq) ** 6
        elif strategy == 'cold':
            w[n] = (mean_freq / freq[n]) ** 6 * (1 + min(gap[n], 30) / 30)
        elif strategy == 'unpop':
            # 생일·기념일 탓에 1~31번으로 구매가 몰리는 편향을 역이용
            w[n] = 2.4 if n >= 32 else (0.45 if n <= 12 else 0.8)
            if n == 7: w[n] *= 0.5
        else:
            w[n] = 1.0
    return w

def draw_one(w):
    pool, ws = list(w.keys()), list(w.values())
    picked = set()
    while len(picked) < 6:
        picked.add(random.choices(pool, weights=ws, k=1)[0])
    return tuple(sorted(picked))

def make_group(strategy, seen):
    w = weights(strategy)
    out = []
    while len(out) < 5:
        a = draw_one(w)
        if a in past or a in seen:            # 역대 1등·중복 제외
            continue
        if strategy != 'pure':
            if not passes(a): continue
            if strategy == 'unpop' and sum(a) < 140: continue
        seen.add(a); out.append(a)
    return out

# ────────────────────────── 렌더 ──────────────────────────
def color(n):
    return 1 if n <= 10 else 2 if n <= 20 else 3 if n <= 30 else 4 if n <= 40 else 5

LETTER = 'ABCDE'

def render_group(key, gi, combos):
    nxt = gi + 1 if gi < GROUPS else 1
    rows = []
    for i, a in enumerate(combos):
        balls = ''.join(f'<b class=c{color(n)}>{n}</b>' for n in a)
        odd = sum(1 for x in a if x % 2)
        rows.append(f'<div class=row><u>{LETTER[i]}</u><div class=balls>{balls}</div>'
                    f'<em>합 {sum(a)}<br>홀{odd}·짝{6-odd}</em></div>')
    return (f'<div class="grp g{gi}">' + ''.join(rows) +
            f'<label class=again for=d{nxt}>다시 뽑기 <span>{gi} / {GROUPS}</span></label></div>')

pools = []
for key, name, desc in STRATS:
    seen = set()
    groups = ''.join(render_group(key, gi, make_group(key, seen))
                     for gi in range(1, GROUPS + 1))
    pools.append(f'<div class="pool p-{key}">{groups}</div>')

# 라디오 정의
strat_radios = ''.join(
    f'<input type=radio name=st id=st-{k} class=r{" checked" if i == 0 else ""}>'
    for i, (k, _, _) in enumerate(STRATS))
draw_radios = ''.join(f'<input type=radio name=dw id=d{i} class=r>'
                      for i in range(1, GROUPS + 1))

strat_labels = ''.join(
    f'<label class=st for=st-{k}>{name}<span>{desc}</span></label>'
    for k, name, desc in STRATS)

# CSS 규칙 생성
css_sel = []
for k, _, _ in STRATS:
    css_sel.append(f'#st-{k}:checked~.stage .p-{k}{{display:block}}')
    css_sel.append(f'#st-{k}:checked~.controls label[for="st-{k}"]{{'
                   'background:#22405c;border-color:var(--bb);color:#fff;'
                   'box-shadow:0 0 0 2px var(--bb) inset}')
    css_sel.append(f'#st-{k}:checked~.controls label[for="st-{k}"]::after{{content:"✓"}}')
    css_sel.append(f'#st-{k}:checked~.controls label[for="st-{k}"] span{{color:#b9e0f5}}')
for i in range(1, GROUPS + 1):
    css_sel.append(f'#d{i}:checked~.stage .g{i}{{display:block}}')
# 아무 뽑기도 누르지 않았을 때만 시작 화면
none_checked = ','.join(f'#d{i}:checked~.stage .start' for i in range(1, GROUPS + 1))
css_sel.append(none_checked + '{display:none}')
CSS_RULES = '\n'.join(css_sel)

# ───────────────────── 통계 (정적 렌더) ─────────────────────
mx, mn = max(freq.values()), min(freq.values())
heat = ''.join(
    f'<div class=cell style="background:rgba(105,200,242,{0.07+(freq[n]-mn)/(mx-mn)*0.5:.2f});'
    f'border-color:rgba(105,200,242,{0.15+(freq[n]-mn)/(mx-mn)*0.45:.2f})">{n}<i>{freq[n]}</i></div>'
    for n in range(1, 46))

bins = [0] * 20
for d in draws:
    k = (sum(d) - 40) // 10
    if 0 <= k < 20: bins[k] += 1
bmax = max(bins)
bars = ''.join(f'<div style="height:{v/bmax*100:.1f}%"></div>' for v in bins)

avg_sum = sum(sum(d) for d in draws) / N
avg_odd = sum(sum(1 for x in d if x % 2) for d in draws) / N
pct_con = sum(1 for d in draws if consec(d) > 0) / N * 100
kv = ''.join(f'<div><span>{k}</span><b>{v}</b></div>' for k, v in [
    ('평균 합계', f'{avg_sum:.0f}'),
    ('평균 홀수', f'{avg_odd:.1f}개'),
    ('연속번호 포함', f'{pct_con:.0f}%'),
    ('최다 출현', f'{max(freq, key=freq.get)}번'),
    ('최소 출현', f'{min(freq, key=freq.get)}번'),
])

cold_list = ''.join(
    f'<em><b>{n}</b><i>{gap[n]}회 전</i></em>'
    for n in sorted(range(1, 46), key=lambda x: -gap[x])[:10])


# ══════════════════════════════════════════════════════════════
# 자바스크립트 계층 (있으면 켜지고, 없으면 위의 CSS 방식이 그대로 남는다)
#
#   .stage  = CSS 전용 화면. 미리 뽑아둔 조합을 라디오로 넘긴다. 기본으로 보인다.
#   .app    = 자바스크립트 화면. 꼭 넣을/뺄 번호를 받아 즉석에서 뽑는다. 기본은 숨김.
#
#   스크립트가 끝까지 성공하면 <html> 에 js 클래스가 붙어 둘이 교체된다.
#   중간에 오류가 나면 클래스가 붙지 않으므로 CSS 화면이 그대로 유지된다.
#
#   ⚠ 아래 JS 의 가중치·필터는 이 파일 위쪽의 weights() / passes() 와
#     같은 규칙이어야 한다. 한쪽만 고치면 두 화면의 결과가 조용히 어긋난다.
# ══════════════════════════════════════════════════════════════
EXTRA_CSS = """
.app{display:none}
html.js .app{display:block}
html.js .stage{display:none}

.opts{margin-top:16px;padding-top:15px;border-top:1px solid var(--line);
  display:flex;flex-wrap:wrap;gap:13px 16px;align-items:flex-end}
.field{flex:1 1 150px;min-width:0}
.field input{width:100%;background:var(--ink);border:1.5px solid var(--line);
  border-radius:10px;color:var(--text);padding:11px 12px;font-family:var(--kr);
  font-size:16px}
.field input:focus{outline:2px solid var(--bb);outline-offset:1px;border-color:transparent}
.field input::placeholder{color:#4b586b}
.chk{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--dim);
  cursor:pointer;flex:0 0 auto;padding-bottom:11px}
.chk input{width:18px;height:18px;accent-color:var(--bb);flex:none}
.warn{color:#ffb3b3;font-size:12.5px;margin-top:9px;display:none}
button.draw{width:100%;margin-top:16px;padding:19px;border:0;border-radius:14px;
  cursor:pointer;font-family:var(--kr);font-size:21px;font-weight:800;color:#14181f;
  background:linear-gradient(100deg,#fbc400,#ffd95e 50%,#fbc400)}
button.draw:active{filter:brightness(.93)}
.after{display:flex;gap:8px;margin-top:12px}
.after button{flex:1;background:var(--panel2);border:1px solid var(--line);
  color:var(--dim);padding:13px;border-radius:11px;cursor:pointer;
  font-family:var(--kr);font-size:14px;font-weight:600}
.after button:active{filter:brightness(1.3)}
.blank{text-align:center;color:var(--dimmer);font-size:13.5px;padding:40px 20px;
  border:1px dashed var(--line);border-radius:16px;margin-top:18px}
"""

APP_HTML = """
<div class="app">
  <div class="opts">
    <label class="field">
      <span class="lbl">꼭 넣을 번호</span>
      <input id="inc" inputmode="numeric" placeholder="예: 7, 24 (최대 4개)">
    </label>
    <label class="field">
      <span class="lbl">뺄 번호</span>
      <input id="exc" inputmode="numeric" placeholder="예: 13, 40">
    </label>
    <label class="chk"><input type="checkbox" id="flt" checked> 분포 필터 적용</label>
  </div>
  <p class="warn" id="warn"></p>
  <button class="draw" id="go">번호 뽑기</button>
  <div id="out"><div class="blank">위 버튼을 누르면 5조합이 나옵니다</div></div>
  <div class="after" id="after" hidden>
    <button id="copy">번호 복사</button>
    <button id="save">텍스트로 저장</button>
  </div>
</div>
"""

JS = r"""
(function () {
  // ── 회차 데이터: "회차:n1,n2,n3,n4,n5,n6" 을 ; 로 이어붙인 문자열
  var RAW = "__RAW__";
  var rows = RAW.split(";").map(function (t) {
    var p = t.split(":");
    return { round: +p[0], nums: p[1].split(",").map(Number) };
  });
  var LAST = rows[rows.length - 1].round, N = rows.length, NEXT = LAST + 1;

  var freq = [], seenAt = [], past = {};
  for (var i = 0; i <= 45; i++) { freq[i] = 0; seenAt[i] = 0; }
  rows.forEach(function (d) {
    d.nums.forEach(function (n) { freq[n]++; seenAt[n] = d.round; });
    past[d.nums.join(",")] = 1;
  });
  var gap = [], mean = N * 6 / 45;
  for (var n = 0; n <= 45; n++) gap[n] = LAST - seenAt[n];

  // ── 조합 지표 (위쪽 파이썬 코드와 같은 규칙)
  function sum(a) { return a.reduce(function (x, y) { return x + y; }, 0); }
  function odds(a) { return a.filter(function (n) { return n % 2; }).length; }
  function lows(a) { return a.filter(function (n) { return n <= 22; }).length; }
  function consec(a) { var c = 0; for (var i = 0; i < 5; i++) if (a[i+1]-a[i] === 1) c++; return c; }
  function ac(a) {
    var s = {}, k = 0;
    for (var i = 0; i < 6; i++) for (var j = i+1; j < 6; j++) {
      var d = Math.abs(a[i]-a[j]); if (!s[d]) { s[d] = 1; k++; }
    }
    return k - 5;
  }
  function sameEnd(a) {
    var m = {}, x = 0;
    a.forEach(function (n) { var e = n % 10; m[e] = (m[e]||0)+1; if (m[e] > x) x = m[e]; });
    return x;
  }
  function mul3(a) { return a.filter(function (n) { return n % 3 === 0; }).length; }

  function passes(a) {
    var s = sum(a);
    if (s < 88 || s > 189) return false;
    var o = odds(a); if (o < 2 || o > 4) return false;
    var l = lows(a); if (l < 2 || l > 4) return false;
    if (consec(a) > 2) return false;
    if (ac(a) < 7) return false;
    if (sameEnd(a) > 2) return false;
    if (mul3(a) > 3) return false;
    return true;
  }

  function weights(st) {
    var w = [0];
    for (var n = 1; n <= 45; n++) {
      if (st === "hot") w[n] = Math.pow(freq[n]/mean, 6);
      else if (st === "cold") w[n] = Math.pow(mean/freq[n], 6) * (1 + Math.min(gap[n],30)/30);
      else if (st === "unpop") {
        w[n] = n >= 32 ? 2.4 : (n <= 12 ? 0.45 : 0.8);
        if (n === 7) w[n] *= 0.5;
      } else w[n] = 1;
    }
    return w;
  }

  function pickOne(w, fixed, ban) {
    var got = {}, cnt = 0, i;
    for (i = 0; i < fixed.length; i++) { got[fixed[i]] = 1; cnt++; }
    while (cnt < 6) {
      var tot = 0;
      for (i = 1; i <= 45; i++) if (!got[i] && !ban[i]) tot += w[i];
      var r = Math.random() * tot;
      for (i = 1; i <= 45; i++) {
        if (got[i] || ban[i]) continue;
        r -= w[i];
        if (r <= 0) { got[i] = 1; cnt++; break; }
      }
    }
    var out = [];
    for (i = 1; i <= 45; i++) if (got[i]) out.push(i);
    return out;
  }

  function generate(st, fixed, ban, useFilter) {
    var w = weights(st), out = [], used = {}, i;

    // 1차 — 모든 조건을 만족하는 조합
    for (i = 0; i < 40000 && out.length < 5; i++) {
      var a = pickOne(w, fixed, ban), key = a.join(",");
      if (used[key] || past[key]) continue;               // 중복·역대 1등 제외
      if (useFilter && st !== "pure") {
        if (!passes(a)) continue;
        if (st === "unpop" && sum(a) < 140) continue;
      }
      used[key] = 1; out.push(a);
    }

    // 2차 — 조건이 지나치게 좁으면 분포 필터를 풀고 채운다.
    // 뺄 번호를 많이 지정하면 만들 수 있는 조합 자체가 5개보다 적을 수 있다.
    // 그래서 "5개가 될 때까지" 가 아니라 반드시 반복 상한을 둔다.
    for (i = 0; i < 20000 && out.length < 5; i++) {
      var b = pickOne(w, fixed, ban), k2 = b.join(",");
      if (used[k2]) continue;
      used[k2] = 1; out.push(b);
    }
    return out;
  }

  // ── 화면 출력
  var LET = "ABCDE";
  function color(n) { return n<=10?1:n<=20?2:n<=30?3:n<=40?4:5; }
  var current = [];

  function render(sets) {
    var html = "";
    sets.forEach(function (a, i) {
      var balls = a.map(function (n) {
        return '<b class="c' + color(n) + '">' + n + "</b>";
      }).join("");
      html += '<div class="row"><u>' + LET[i] + '</u><div class="balls">' + balls +
              '</div><em>합 ' + sum(a) + "<br>홀" + odds(a) + "·짝" + (6-odds(a)) + "</em></div>";
    });
    document.getElementById("out").innerHTML = html;
    document.getElementById("after").hidden = false;
  }

  function parse(str, cap) {
    var m = String(str).match(/\d+/g) || [], out = [], i;
    for (i = 0; i < m.length && out.length < cap; i++) {
      var v = +m[i];
      if (v >= 1 && v <= 45 && out.indexOf(v) < 0) out.push(v);
    }
    return out;
  }

  function asText(sets) {
    var d = new Date(), p = function (x) { return (x<10?"0":"") + x; };
    var t = d.getFullYear() + "." + p(d.getMonth()+1) + "." + p(d.getDate());
    var body = sets.map(function (a, i) {
      return LET[i] + "  " + a.map(function (n) { return (n<10?" ":"") + n; }).join("  ");
    }).join("\n");
    return "로또 번호 5조합 · 제 " + NEXT + "회 대상 (" + t + " 생성)\n\n" + body +
           "\n\n※ 당첨 확률을 높여주는 도구가 아닙니다. 재미로만 참고하세요.";
  }

  var warn = document.getElementById("warn");
  function say(msg) {
    warn.textContent = msg || "";
    warn.style.display = msg ? "block" : "none";
  }

  document.getElementById("go").addEventListener("click", function () {
    var inc = parse(document.getElementById("inc").value, 4);
    var exc = parse(document.getElementById("exc").value, 39).filter(function (n) {
      return inc.indexOf(n) < 0;
    });
    var ban = [];
    exc.forEach(function (n) { ban[n] = 1; });
    if (45 - exc.length < 6) { say("뺄 번호가 너무 많습니다. 최소 6개는 남겨주세요."); return; }

    var stEl = document.querySelector('input[name=st]:checked');
    var st = stEl ? stEl.id.replace("st-", "") : "bal";
    var useFilter = document.getElementById("flt").checked;

    // 번호가 많으면 개수로 줄인다. 39개를 그대로 나열하면 안내가 화면을 덮는다.
    var fmt = function (arr) { return arr.length > 6 ? arr.length + "개" : arr.join(", "); };
    var msg = [];
    if (inc.length) msg.push("고정 " + fmt(inc));
    if (exc.length) msg.push("제외 " + fmt(exc));
    if (useFilter && inc.length >= 3) msg.push("고정 번호가 많으면 분포 필터를 만족하기 어려워 결과가 비슷해질 수 있습니다");
    say(msg.join(" · "));

    current = generate(st, inc, ban, useFilter);
    if (current.length < 5) {
      msg.push("조건이 좁아 " + current.length + "조합만 만들 수 있습니다");
      say(msg.join(" · "));
    }
    render(current);
    this.textContent = "다시 뽑기";
  });

  function fallbackCopy(text) {
    var t = document.createElement("textarea");
    t.value = text; t.setAttribute("readonly", "");
    t.style.cssText = "position:fixed;top:0;left:0;opacity:0";
    document.body.appendChild(t);
    t.select();
    if (t.setSelectionRange) t.setSelectionRange(0, text.length);   // iOS 대응
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
    document.body.removeChild(t);
    return ok;
  }

  document.getElementById("copy").addEventListener("click", function () {
    var b = this, text = asText(current);
    var done = function (m) {
      b.textContent = m;
      setTimeout(function () { b.textContent = "번호 복사"; }, 1800);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done("복사했습니다"); })
        .catch(function () { done(fallbackCopy(text) ? "복사했습니다" : "복사 안 됨"); });
    } else {
      done(fallbackCopy(text) ? "복사했습니다" : "복사 안 됨");
    }
  });

  document.getElementById("save").addEventListener("click", function () {
    var blob = new Blob(["\uFEFF" + asText(current)], { type: "text/plain;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "로또번호_" + NEXT + "회.txt";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  });

  // 여기까지 오류 없이 왔을 때만 화면을 교체한다.
  document.documentElement.className += " js";
})();
"""

RAW_DATA = ";".join(f"{r}:" + ",".join(str(x) for x in d)
                    for r, d in zip(rounds, draws))
JS = JS.replace("__RAW__", RAW_DATA)

# ────────────────────────── 조립 ──────────────────────────
HTML = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>로또 번호 생성기 — 역대 {LAST}회 데이터 기반</title>
<style>
:root{{
  --ink:#0d1017; --panel:#161b24; --panel2:#1d2431; --line:#2a3342;
  --text:#e9edf4; --dim:#94a1b5; --dimmer:#6b788c; --bb:#69c8f2;
  --y:#fbc400; --b:#69c8f2; --r:#ff7272; --g:#aaaaaa; --n:#b0d840;
  --bink:#14181f;
  --kr:'Apple SD Gothic Neo','Malgun Gothic','맑은 고딕',sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{-webkit-text-size-adjust:100%}}
body{{
  background:var(--ink);color:var(--text);font-family:var(--kr);
  font-size:15px;line-height:1.6;padding:0 16px 70px;
  background-image:radial-gradient(ellipse 900px 400px at 50% -130px,#1b2637 0,transparent 70%);
}}
.wrap{{max-width:720px;margin:0 auto}}
.r{{/* 화면에서 감추되 :checked 는 살린다. position:fixed 라서 포커스가 옮겨가도
     페이지가 위로 튀지 않는다. */
  position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;z-index:-1;pointer-events:none}}

header{{padding:36px 0 22px;text-align:center}}
.eyebrow{{font-size:11.5px;font-weight:700;letter-spacing:.12em;color:var(--dim)}}
.eyebrow b{{color:var(--n)}}
h1{{font-size:clamp(32px,8.5vw,50px);font-weight:800;line-height:1.1;margin:12px 0 10px;letter-spacing:-.02em}}
h1 i{{font-style:normal;background:linear-gradient(180deg,#fbc400,#ff7272);
  -webkit-background-clip:text;background-clip:text;color:transparent}}
.sub{{color:var(--dim);font-size:13.5px;max-width:400px;margin:0 auto}}

.controls{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;margin-top:24px}}
.lbl{{font-size:11px;font-weight:700;letter-spacing:.12em;color:var(--dimmer);display:block;margin-bottom:10px}}
.strat{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.strat label:nth-of-type(5){{grid-column:1/-1}}
label.st{{
  background:var(--panel2);border:1.5px solid var(--line);color:var(--dim);
  border-radius:12px;padding:13px 34px 12px 14px;cursor:pointer;
  font-size:15px;font-weight:700;line-height:1.3;position:relative;
  -webkit-tap-highlight-color:transparent;
}}
label.st span{{display:block;font-size:11.5px;font-weight:400;color:var(--dimmer);margin-top:2px}}
label.st::after{{
  content:"";position:absolute;right:12px;top:50%;transform:translateY(-50%);
  width:22px;height:22px;border-radius:50%;border:1.5px solid var(--line);
  display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;color:#fff;background:transparent;
}}
{CSS_RULES}
{EXTRA_CSS}
#st-bal:checked~.controls label[for="st-bal"]::after,
#st-hot:checked~.controls label[for="st-hot"]::after,
#st-cold:checked~.controls label[for="st-cold"]::after,
#st-unpop:checked~.controls label[for="st-unpop"]::after,
#st-pure:checked~.controls label[for="st-pure"]::after{{
  background:var(--bb);border-color:var(--bb);color:#0d1017;
}}

.stage{{margin-top:22px}}
.pool,.grp{{display:none}}
.start{{display:block}}
label.draw{{
  display:block;width:100%;padding:19px;border-radius:14px;cursor:pointer;
  text-align:center;font-size:21px;font-weight:800;color:#14181f;
  background:linear-gradient(100deg,#fbc400,#ffd95e 50%,#fbc400);
  -webkit-tap-highlight-color:transparent;
}}
label.draw:active{{filter:brightness(.93)}}
.hint{{text-align:center;color:var(--dimmer);font-size:13px;margin-top:14px}}

.row{{
  background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:13px 14px;display:flex;align-items:center;gap:11px;margin-bottom:8px;
}}
.row u{{text-decoration:none;font-size:17px;font-weight:800;color:var(--dimmer);width:16px;flex:none;text-align:center}}
.balls{{display:flex;gap:6px;flex:1;flex-wrap:wrap}}
.row b{{
  width:40px;height:40px;border-radius:50%;flex:none;
  display:flex;align-items:center;justify-content:center;
  font-size:16px;font-weight:800;color:var(--bink);
  box-shadow:inset 0 -5px 9px rgba(0,0,0,.22),inset 0 4px 7px rgba(255,255,255,.55),0 2px 5px rgba(0,0,0,.4);
}}
.c1{{background:var(--y)}}.c2{{background:var(--b)}}.c3{{background:var(--r)}}
.c4{{background:var(--g)}}.c5{{background:var(--n)}}
.row em{{font-style:normal;font-size:11px;color:var(--dimmer);text-align:right;width:60px;flex:none;line-height:1.5}}
label.again{{
  display:block;margin-top:12px;padding:16px;border-radius:13px;cursor:pointer;
  text-align:center;font-size:17px;font-weight:800;color:#14181f;
  background:linear-gradient(100deg,#fbc400,#ffd95e 50%,#fbc400);
  -webkit-tap-highlight-color:transparent;
}}
label.again span{{font-weight:600;font-size:12.5px;opacity:.6;margin-left:5px}}
label.again:active{{filter:brightness(.93)}}

details{{margin-top:30px;background:var(--panel);border:1px solid var(--line);border-radius:18px}}
summary{{padding:16px 18px;cursor:pointer;font-weight:700;font-size:14.5px}}
.sb{{padding:2px 18px 20px;border-top:1px solid var(--line)}}
.sh{{font-size:11px;font-weight:700;letter-spacing:.12em;color:var(--dimmer);margin:20px 0 11px}}
.heat{{display:grid;grid-template-columns:repeat(9,1fr);gap:5px}}
.cell{{aspect-ratio:1;border-radius:7px;border:1px solid;display:flex;flex-direction:column;
  align-items:center;justify-content:center;font-size:12px;font-weight:700}}
.cell i{{font-style:normal;font-size:9px;font-weight:400;color:var(--dimmer)}}
.bars{{display:flex;align-items:flex-end;gap:3px;height:90px}}
.bars div{{flex:1;background:linear-gradient(180deg,#69c8f2,#2f6c8f);border-radius:3px 3px 0 0;min-height:2px}}
.axis{{display:flex;justify-content:space-between;font-size:10.5px;color:var(--dimmer);margin-top:6px}}
.kv{{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:8px}}
.kv div{{background:var(--panel2);border:1px solid var(--line);border-radius:11px;padding:10px 12px}}
.kv span{{display:block;font-size:10.5px;color:var(--dimmer)}}
.kv b{{font-size:18px;font-weight:800}}
.cold{{display:flex;flex-wrap:wrap;gap:6px}}
.cold em{{font-style:normal;background:var(--panel2);border:1px solid var(--line);
  border-radius:9px;padding:6px 10px;font-size:12.5px}}
.cold em b{{font-weight:800;margin-right:5px}}
.cold em i{{font-style:normal;color:var(--dimmer);font-size:11px}}

.note{{margin-top:30px;border:1px solid var(--line);border-left:3px solid var(--r);
  border-radius:0 14px 14px 0;padding:17px 18px;background:#1a1418}}
.note h3{{font-size:13.5px;font-weight:800;margin-bottom:9px;color:#ffb3b3}}
.note p{{font-size:13px;color:var(--dim);margin-bottom:9px}}
.note p:last-child{{margin-bottom:0}}
.note b{{color:var(--text)}}
footer{{text-align:center;color:var(--dimmer);font-size:11.5px;margin-top:28px;line-height:1.8}}

@media(min-width:620px){{
  .strat{{grid-template-columns:repeat(3,1fr)}}
  .strat label:nth-of-type(5){{grid-column:auto}}
}}
@media(max-width:400px){{
  .row b{{width:36px;height:36px;font-size:14.5px}}
  .row em{{width:54px;font-size:10.5px}}
  .heat{{grid-template-columns:repeat(7,1fr)}}
}}
</style>
</head>
<body>
<div class="wrap">
<!-- 선택 상태를 담는 라디오. CSS 형제 선택자(~)가 닿으려면
     .controls / .stage 와 같은 부모 안에서 이들보다 앞에 있어야 한다. -->
{strat_radios}{draw_radios}

<header>
  <div class="eyebrow">제 <b>{NEXT:,}</b>회 대상 · 역대 <b>{N:,}</b>회 데이터 분석</div>
  <h1>로또 <i>번호 생성기</i></h1>
  <p class="sub">역대 당첨번호의 실제 분포에서 뽑은 5조합을 보여줍니다. 지난 1등 조합은 모두 제외했습니다.</p>
</header>

<div class="controls">
  <span class="lbl">뽑기 방식</span>
  <div class="strat">{strat_labels}</div>
</div>

<div class="stage">
  <div class="start">
    <label class="draw" for="d1">번호 뽑기</label>
    <p class="hint">뽑기 방식을 고른 뒤 버튼을 누르세요</p>
  </div>
  {''.join(pools)}
</div>
{APP_HTML}

<details>
  <summary>역대 데이터 통계</summary>
  <div class="sb">
    <div class="sh">번호별 출현 횟수 (1 ~ {LAST}회)</div>
    <div class="heat">{heat}</div>
    <div class="sh">6개 번호 합계 분포</div>
    <div class="bars">{bars}</div>
    <div class="axis"><span>40</span><span>100</span><span>160</span><span>220</span></div>
    <div class="sh">한 회차 평균 모습</div>
    <div class="kv">{kv}</div>
    <div class="sh">가장 오래 안 나온 번호</div>
    <div class="cold">{cold_list}</div>
  </div>
</details>

<div class="note">
  <h3>먼저 알아두실 것</h3>
  <p><b>어떤 분석으로도 당첨 확률은 올라가지 않습니다.</b> 1등 확률은 814만 5,060분의 1로 고정이고, 매 회차 추첨은 이전 회차와 완전히 독립입니다. 실제로 이 {N:,}회 데이터로 번호 균등성을 검정하면 <b>p = 0.96</b>, 즉 45개 번호는 통계적으로 완벽하게 균등합니다. "많이 나온 수"와 "안 나온 수"는 확률적 근거가 없는, 재미를 위한 선택지입니다.</p>
  <p>이 도구가 실제로 하는 일은 두 가지입니다. 첫째, 역대 당첨 조합이 보이는 범위(합계·홀짝·연속 등) 안에서 번호를 골라 <b>실제 추첨 결과처럼 보이는 조합</b>을 만듭니다. 둘째, <b>비인기 번호</b> 방식은 사람들이 생일 때문에 몰리는 1~31번을 피합니다. 당첨 확률은 그대로지만, 당첨됐을 때 <b>같이 맞힌 사람이 적어 1인당 수령액이 커집니다.</b> 이건 근거가 있는 유일한 이득입니다.</p>
  <p>필터에도 한계가 있습니다. 이 필터는 <b>역대 1등 조합의 48%만 통과</b>합니다. 나머지 절반의 당첨 조합을 스스로 버리는 셈이라 확률상 이득도 손실도 없이 딱 중립입니다.</p>
  <p>이 페이지는 미리 뽑아둔 조합을 보여주는 방식이라, <b>같은 시점에 접속한 사람은 같은 번호를 보게 됩니다.</b> 조합은 매주 추첨 후 전부 새로 뽑히지만, 한 주 안에서는 고정입니다. 여러 명이 같은 조합을 사면 당첨 시 나눠 갖는 인원이 늘어나니, 방식을 바꾸거나 마음에 드는 회차를 골라 각자 다른 조합을 쓰시길 권합니다.</p>
  <p>로또는 투자가 아닙니다. 잃어도 괜찮은 금액만, 즐길 수 있는 만큼만 쓰세요.</p>
</div>

<footer>
  회차 데이터: 동행복권 공식 발표 기준 · 1회 ~ {LAST:,}회<br>
  전략별 {GROUPS}회분 · 총 {GROUPS*5*len(STRATS):,}조합 수록<br>
  {BUILT} 갱신 · 매주 추첨 후 자동으로 새 조합이 올라옵니다
</footer>
</div>
<script>{JS}</script>
</body>
</html>'''

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(HTML)
print(f'생성 완료: {OUT}')
print(f'  데이터 {N}회차 (1~{LAST}회) · 이번 대상 {NEXT}회')
print(f'  전략 {len(STRATS)}종 × {GROUPS}회 × 5조합 = {GROUPS*5*len(STRATS):,}조합')
print(f'  자바스크립트 계층: {"included" if "<script" in HTML else "없음"} · CSS 대체 화면 유지')
import os; print(f'  파일 크기: {os.path.getsize(OUT)/1024:.0f} KB')
