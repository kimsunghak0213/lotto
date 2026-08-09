# -*- coding: utf-8 -*-
"""
draws.csv 에 새 회차를 채워 넣는다.

경로가 두 개다.

1) 동행복권 공식 API
   가장 정확하지만, 동행복권이 TRACER 라는 차단 시스템으로 해외 IP 를 막고 있다.
   깃허브 서버는 미국에 있어 현재 차단 대상이며, JSON 대신 차단 안내 HTML 이 온다.

2) 깃허브에 있는 대체 저장소 (smok95/lotto)
   1회부터 최신회까지의 추첨결과를 JSON 으로 공개한다.
   깃허브에서 깃허브를 읽는 것이라 차단될 일이 없다.

공식을 먼저 시도하고, 막혔을 때만 대체 경로를 쓴다.
차단이 풀리면 자동으로 공식으로 돌아간다.

대체 경로를 쓸 때는 이미 갖고 있는 회차를 전부 대조해서 하나라도 다르면
쓰지 않는다. 남의 저장소를 믿고 쓰는 만큼, 조용히 틀린 값이 섞이는 것을 막는다.

어느 쪽도 안 되면 오류로 끝내지 않는다. 기존 데이터로 사이트를 다시 만들면
되기 때문이다. 자동 갱신이 한 주 실패해도 페이지가 죽지는 않는다.
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'draws.csv')
HEADER = ['round', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'bonus']

OFFICIAL = 'https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}'
MIRROR = 'https://raw.githubusercontent.com/smok95/lotto/main/results/all.json'

MAX_NEW = 20          # 한 번에 받아올 최대 회차 수 (무한 루프 방지)
TIMEOUT = 20


def load():
    with open(CSV_PATH, encoding='utf-8') as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != HEADER:
        raise SystemExit('draws.csv 형식이 다릅니다. 첫 줄은 %s 여야 합니다.' % ','.join(HEADER))
    return [[int(x) for x in r] for r in rows[1:] if r]


def save(rows):
    rows.sort(key=lambda r: r[0])
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


def get(url):
    req = urllib.request.Request(url, headers={
        # 기본 파이썬 UA 는 차단될 수 있어 브라우저 UA 를 쓴다
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://www.dhlottery.co.kr/',
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read().decode('utf-8')


def check(no, nums, bonus):
    """받아온 값이 정상인지 확인한다. 이상한 값이 섞이면 통계와 필터가 조용히 어긋난다."""
    if len(set(nums)) != 6:
        raise ValueError('%d회 번호에 중복이 있습니다: %s' % (no, nums))
    if not all(1 <= n <= 45 for n in list(nums) + [bonus]):
        raise ValueError('%d회 번호가 1~45 범위를 벗어났습니다: %s, 보너스 %s' % (no, nums, bonus))
    if bonus in nums:
        raise ValueError('%d회 보너스(%d)가 당첨번호와 겹칩니다' % (no, bonus))
    return [no] + sorted(nums) + [bonus]


# ───────────────────────── 공식 API ─────────────────────────
def from_official(last):
    """
    (받은 회차 목록, 정상 확인 여부) 를 돌려준다.
    차단·오류로 못 받았으면 두 번째 값이 False 가 되어 대체 경로로 넘어간다.
    """
    added = []
    for no in range(last + 1, last + 1 + MAX_NEW):
        try:
            d = json.loads(get(OFFICIAL.format(no)))
        except json.JSONDecodeError:
            # JSON 이 아니라 HTML 이 왔다는 뜻. 차단 안내 화면일 가능성이 크다.
            print('  %d회 응답이 JSON 이 아닙니다 (차단 가능성)' % no)
            return added, False
        except (urllib.error.URLError, OSError) as e:
            print('  %d회 연결 실패: %s' % (no, getattr(e, 'reason', e)))
            return added, False

        if d.get('returnValue') != 'success':
            print('  %d회는 아직 추첨 전입니다' % no)
            return added, True          # 정상적으로 "없음" 을 확인했다
        if int(d['drwNo']) != no:
            print('  %d회를 요청했는데 %s회가 왔습니다' % (no, d['drwNo']))
            return added, False

        row = check(no, [int(d['drwtNo%d' % i]) for i in range(1, 7)], int(d['bnusNo']))
        added.append(row)
        print('  %d회 추가: %s + 보너스 %d' % (no, row[1:7], row[7]))
        time.sleep(0.4)
    return added, True


# ──────────────────────── 대체 저장소 ────────────────────────
def from_mirror(rows, last):
    print('  대체 저장소에서 받아옵니다')
    try:
        data = json.loads(get(MIRROR))
    except Exception as e:
        print('  대체 저장소도 실패: %s' % e)
        return []

    theirs = {}
    for d in data:
        try:
            n = int(d['draw_no'])
            theirs[n] = check(n, [int(x) for x in d['numbers']], int(d['bonus_no']))
        except (ValueError, KeyError, TypeError):
            continue          # 이상한 항목은 버린다
    print('  대체 저장소: %d회차 (최신 %d회)' % (len(theirs), max(theirs) if theirs else 0))

    # 이미 가진 회차를 전부 대조한다. 하나라도 다르면 이 출처를 믿지 않는다.
    mismatch = [r[0] for r in rows if r[0] in theirs and theirs[r[0]] != r]
    if mismatch:
        print('  기존 데이터와 다른 회차가 %d건 있어 사용하지 않습니다: %s'
              % (len(mismatch), mismatch[:5]))
        return []
    checked = sum(1 for r in rows if r[0] in theirs)
    print('  기존 %d회차와 전부 일치 — 신뢰 가능' % checked)

    new = [theirs[n] for n in sorted(theirs) if n > last][:MAX_NEW]
    for row in new:
        print('  %d회 추가: %s + 보너스 %d' % (row[0], row[1:7], row[7]))
    return new


def main():
    rows = load()
    last = max(r[0] for r in rows)
    print('현재 데이터: %d회차 (최신 %d회)' % (len(rows), last))

    print('동행복권 공식 API 시도')
    added, ok = from_official(last)

    if not added and not ok:
        added = from_mirror(rows, last)

    if not added:
        print('새 회차 없음 — 기존 데이터로 진행합니다')
        return 0

    rows.extend(added)
    save(rows)
    print('%d회차 추가 완료 → 최신 %d회' % (len(added), max(r[0] for r in rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
