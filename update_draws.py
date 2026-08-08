# -*- coding: utf-8 -*-
"""
draws.csv 에 새 회차를 채워 넣는다.

동행복권이 회차별 당첨번호를 JSON으로 돌려주는 주소를 쓴다.
아직 추첨하지 않은 회차는 returnValue 가 "fail" 로 오므로,
마지막 회차 다음부터 fail 이 나올 때까지 이어서 받는다.

네트워크가 막히거나 응답이 이상해도 스크립트는 실패로 끝내지 않는다.
받아온 게 없으면 기존 데이터로 사이트를 그대로 다시 만들면 되기 때문이다.
(자동 갱신이 하루 실패해도 페이지가 죽지 않게 하려는 의도)
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'draws.csv')
API = 'https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}'
HEADER = ['round', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'bonus']
MAX_NEW = 20          # 한 번에 받아올 최대 회차 수 (무한 루프 방지)
TIMEOUT = 15


def load():
    with open(CSV_PATH, encoding='utf-8') as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != HEADER:
        raise SystemExit(f'draws.csv 형식이 다릅니다. 첫 줄은 {",".join(HEADER)} 여야 합니다.')
    return [[int(x) for x in r] for r in rows[1:] if r]


def fetch(no):
    """해당 회차를 받아온다. 아직 추첨 전이면 None."""
    req = urllib.request.Request(
        API.format(no),
        headers={
            # 기본 파이썬 UA 는 차단될 수 있어 브라우저 UA 를 쓴다
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://www.dhlottery.co.kr/',
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        d = json.loads(res.read().decode('utf-8'))

    if d.get('returnValue') != 'success':
        return None

    nums = sorted(int(d[f'drwtNo{i}']) for i in range(1, 7))
    bonus = int(d['bnusNo'])

    # 받아온 값이 정상인지 확인한다. 이상한 값이 데이터에 섞이면
    # 이후 통계와 필터가 전부 조용히 어긋난다.
    if len(set(nums)) != 6:
        raise ValueError(f'{no}회 번호에 중복이 있습니다: {nums}')
    if not all(1 <= n <= 45 for n in nums + [bonus]):
        raise ValueError(f'{no}회 번호가 1~45 범위를 벗어났습니다: {nums}, 보너스 {bonus}')
    if bonus in nums:
        raise ValueError(f'{no}회 보너스({bonus})가 당첨번호와 겹칩니다')
    if int(d['drwNo']) != no:
        raise ValueError(f'{no}회를 요청했는데 {d["drwNo"]}회가 왔습니다')

    return [no] + nums + [bonus]


def main():
    rows = load()
    last = max(r[0] for r in rows)
    print(f'현재 데이터: {len(rows)}회차 (최신 {last}회)')

    added = []
    for no in range(last + 1, last + 1 + MAX_NEW):
        try:
            got = fetch(no)
        except urllib.error.URLError as e:
            print(f'  {no}회 연결 실패: {e.reason} — 이번 갱신은 건너뜁니다')
            break
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f'  {no}회 응답 이상: {e} — 이번 갱신은 건너뜁니다')
            break

        if got is None:
            print(f'  {no}회는 아직 추첨 전입니다')
            break

        added.append(got)
        print(f'  {no}회 추가: {got[1:7]} + 보너스 {got[7]}')
        time.sleep(0.4)          # 연속 요청 간 간격

    if not added:
        print('새 회차 없음 — 기존 데이터로 진행합니다')
        return 0

    rows.extend(added)
    rows.sort(key=lambda r: r[0])
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f'{len(added)}회차 추가 완료 → 최신 {rows[-1][0]}회')
    return 0


if __name__ == '__main__':
    sys.exit(main())
