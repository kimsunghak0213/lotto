# -*- coding: utf-8 -*-
"""
1등·2등 배출점을 받아와 stores.json 으로 저장한다.

브라우저에서 당첨판매점 페이지를 직접 열면 errorPage 로 튕기는데,
이는 모바일 감지 스크립트 때문으로 보인다. 서버에서 받아올 때는
그 스크립트가 실행되지 않으므로 원본 화면을 그대로 받을 수 있다.

주소 구조가 언제든 바뀔 수 있어 후보를 여러 개 두고 차례로 시도한다.
표의 생김새도 특정하지 않고, "자동/수동/반자동" 이 들어 있는 행을
배출점으로 보는 방식이라 화면이 조금 바뀌어도 견딘다.

전부 실패해도 오류로 끝내지 않는다. 그 경우 사이트는 검색 링크를
그대로 보여주므로 기능이 사라지지는 않는다.
"""
import csv
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, 'draws.csv')
OUT_PATH = os.path.join(HERE, 'stores.json')
TIMEOUT = 20

# 데스크톱 브라우저인 척한다. 모바일로 인식되면 다른 화면으로 넘어간다.
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

CANDIDATES = [
    'https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={n}&nowPage=1',
    'https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={n}',
    'https://www.dhlottery.co.kr/wnprchsplcsrch/home?drwNo={n}',
    'https://www.dhlottery.co.kr/wnprchsplcsrch/list?drwNo={n}',
]

# 조회 페이지가 세션을 요구할 때를 대비해 먼저 들르는 곳
WARMUP = 'https://www.dhlottery.co.kr/common.do?method=main'

RANK_WORDS = ('자동', '수동', '반자동')


class Tables(HTMLParser):
    """문서 안의 모든 표를 행·칸 단위로 뽑아낸다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.rows, self.cells, self.buf = [], [], [], []
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.rows = []
        elif tag == 'tr':
            self.cells = []
        elif tag in ('td', 'th'):
            self.in_cell, self.buf = True, []

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_cell:
            text = re.sub(r'\s+', ' ', ''.join(self.buf)).strip()
            self.cells.append(text)
            self.in_cell = False
        elif tag == 'tr':
            if self.cells:
                self.rows.append(self.cells)
            self.cells = []
        elif tag == 'table':
            if self.rows:
                self.tables.append(self.rows)
            self.rows = []

    def handle_data(self, data):
        if self.in_cell:
            self.buf.append(data)


# 조회 페이지가 세션을 요구하는 경우가 있어 쿠키를 들고 다닌다.
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(CookieJar()))


def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Referer': 'https://www.dhlottery.co.kr/',
        'Accept-Language': 'ko-KR,ko;q=0.9',
    })
    with _opener.open(req, timeout=TIMEOUT) as res:
        raw = res.read()
        final = res.geturl()
    if final != url:
        print(f'    (전달됨 → {final})')
    for enc in ('utf-8', 'euc-kr', 'cp949'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def pick_stores(doc):
    """
    표에서 배출점 행만 골라낸다.
    칸이 3개 이상이고, 어느 칸엔가 자동/수동/반자동 이 들어 있으며,
    주소처럼 보이는 칸(시/도 이름으로 시작)이 있는 행을 배출점으로 본다.
    """
    p = Tables()
    p.feed(doc)
    found = []
    for rows in p.tables:
        for cells in rows:
            if len(cells) < 3:
                continue
            kind = next((c for c in cells if c in RANK_WORDS), None)
            if not kind:
                continue
            addr = next((c for c in cells
                         if re.match(r'^(서울|부산|대구|인천|광주|대전|울산|세종|'
                                     r'경기|강원|충북|충남|전북|전남|경북|경남|제주)', c)), None)
            if not addr:
                continue
            # 이름은 번호·구분·주소를 뺀 나머지 중 가장 긴 칸
            rest = [c for c in cells
                    if c is not kind and c is not addr and not c.isdigit() and c]
            name = max(rest, key=len) if rest else ''
            if name:
                found.append({'name': name, 'type': kind, 'addr': addr})
    # 같은 판매점이 여러 번 나오면 횟수로 묶는다 (한 곳에서 2장 이상 나온 경우)
    merged, order = {}, []
    for s in found:
        key = (s['name'], s['addr'])
        if key in merged:
            merged[key]['count'] += 1
        else:
            merged[key] = dict(s, count=1)
            order.append(key)
    return [merged[k] for k in order]


def clean(doc):
    """진단용으로 스크립트·스타일을 걷어낸다. 안 그러면 암호화 스크립트가 화면을 덮는다."""
    d = re.sub(r'(?is)<script.*?</script>', ' ', doc)
    d = re.sub(r'(?is)<style.*?</style>', ' ', d)
    return d


def diagnose(doc):
    """표를 못 읽었을 때 무엇이 들어 있는지 알려준다."""
    d = clean(doc)
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', d)).strip()
    print(f'    표를 찾지 못했습니다. 본문 앞부분: {text[:180]}')

    for w in ('자동', '수동', '배출점', '당첨판매점', '조회', '로그인', '없습니다'):
        c = d.count(w)
        if c:
            print(f'      "{w}" {c}회 등장')

    p = Tables()
    p.feed(d)
    print(f'      표 {len(p.tables)}개')
    for i, rows in enumerate(p.tables[:6]):
        head = rows[0] if rows else []
        print(f'        표{i + 1}: {len(rows)}행 · 첫 행 {[c[:14] for c in head[:6]]}')
        if len(rows) > 1:
            print(f'                       둘째 행 {[c[:14] for c in rows[1][:6]]}')

    # 자동/수동 이 본문에 있으면 그 주변을 보여준다. 표가 아닌 목록일 수 있다.
    m = re.search(r'(자동|수동)', text)
    if m:
        a = max(0, m.start() - 90)
        print(f'      "자동/수동" 주변: …{text[a:m.start() + 110]}…')


def main():
    with open(CSV_PATH, encoding='utf-8') as f:
        rounds = [int(r[0]) for r in list(csv.reader(f))[1:] if r]
    n = max(rounds)
    print(f'{n}회 배출점을 찾습니다')

    try:
        get(WARMUP)          # 세션 쿠키를 받아둔다
        print('  메인 방문 완료 (세션 확보)')
    except Exception as e:
        print(f'  메인 방문 실패: {e} — 그대로 진행합니다')

    for url in CANDIDATES:
        u = url.format(n=n)
        try:
            doc = get(u)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f'  실패: {u} ({getattr(e, "reason", e)})')
            time.sleep(0.5)
            continue

        stores = pick_stores(doc)
        print(f'  받음: {u} — {len(doc):,}자, 배출점 {len(stores)}곳')
        if stores:
            data = {'round': n, 'source': u, 'stores': stores}
            with open(OUT_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            print(f'  저장 완료 — {n}회 {len(stores)}곳')
            for s in stores[:5]:
                print(f'    · {s["name"]} ({s["type"]}) {s["addr"]}')
            return 0
        diagnose(doc)

    print('배출점을 가져오지 못했습니다 — 사이트는 검색 링크로 대신 동작합니다')
    if not os.path.exists(OUT_PATH):
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump({'round': n, 'source': '', 'stores': []}, f, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
