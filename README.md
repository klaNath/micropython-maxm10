# micropython-maxm10

u-blox MAX-M10（M10 SPG 5.10）を MicroPython から設定・利用するためのドライバです。
RP2350 + MAX-M10M-00B で動作確認しています。

- UART の通信速度の自動検出と変更
- CFG-VALSET / VALGET による設定。BBR に保存済みのものは書き込まないので、起動毎に呼んでよい
- 受信ストリームを NMEA と UBX に分離。設定や問い合わせ中も NMEA はアプリへ渡され続ける
- AssistNow Autonomous などの状態取得（NAV-AOPSTATUS / NAV-SAT / NAV-STATUS）

## インストール

```
mpremote mip install github:klaNath/micropython-maxm10
```

または `maxm10/` をボードの `/lib/maxm10/` へコピーします。

```
mpremote cp -r maxm10 :lib/
```

## 使い方

```python
from maxm10 import MaxM10, signals, sbas_prnscanmask, SBAS_PRN_MSAS, DYN_AUTOMOTIVE

def on_nmea(line):        # bytes, CR LF 付き、チェックサム検証済み
    ...

gnss = MaxM10(uart_id=0, tx=0, rx=1, resetn=6, pps=22, on_nmea=on_nmea, log=print)
gnss.begin(115200)        # 検出 → 115200 へ変更 → ホスト側 UART も 115200 で開く
gnss.apply(
    signals(gps=True, gal=True, glo=True, qzss=True, qzss_l1s=True, sbas=True),
    [('CFG-NAVSPG-DYNMODEL', DYN_AUTOMOTIVE),
     ('CFG-SBAS-PRNSCANMASK', sbas_prnscanmask(SBAS_PRN_MSAS)),
     ('CFG-ANA-USE_ANA', 1)],
)

while True:
    gnss.update()         # 受信分を NMEA / UBX に振り分け（ノンブロッキング）
```

asyncio では `asyncio.create_task(gnss.run())` で受信タスクを動かせます（`examples/async_reader.py`）。

### 主な API

| メソッド | 内容 |
|---|---|
| `begin(baud, reset=False)` | モジュールを探し、通信速度を設定。`reset=True` は RESET_N によるハードリセット（復旧用） |
| `apply(*groups, layers=RAM\|BBR)` | 設定の書き込みと検証。1 グループ = 1 回の VALSET |
| `valset(items)` / `valget(keys, layer)` | 設定の直接書き込み / 読み出し |
| `update()` / `run()` | 受信処理（同期 / asyncio） |
| `poll_aop()` / `poll_sat()` / `poll_nav_status()` / `poll_version()` | 状態の問い合わせ。結果は `aop` / `sat` / `nav_status` / `version` にも保持 |
| `send(cls, id, payload)` | 応答を待たずに UBX を送信。応答は `on_ubx` と上記の属性で受け取る |

設定キーは名前（`maxm10/keys.py` にあるもの）またはキー ID（int）で指定できます。
状態は `CFG-MSGOUT-UBX_NAV_*_UART1` で周期出力させると、問い合わせなしで属性が更新されます。

動作確認用に `maxm10.monitor.monitor(gnss, seconds)` があります（GGA と状態を表示）。

## 注意

- **RESET_N は BBR と RTC を消去します。** 設定・エフェメリス・AssistNow Autonomous のデータが失われ、コールドスタートになります。ドライバは `hard_reset()` 以外で RESET_N を駆動しません（コンストラクタで入力に戻します）。
- MAX-M10M には Flash がありません。設定は RAM と BBR に保存されます。電源断後も設定を保つには V_BCKP の供給が必要です。
- TIMEPULSE は SAFEBOOT_N と兼用です。起動時に Low だと safeboot モードに入るため、`hard_reset()` 中は `pps` ピンを High に保ちます。
- `signals()` の結果は 1 グループで送ってください。途中の組み合わせは受信機に拒否されることがあり、信号設定の変更は GNSS サブシステムの再起動を伴います。
- `request()` 系はブロッキングです（最大 1.5 秒）。待ち時間中も受信は処理され、NMEA は `on_nmea` に渡されます。

## テスト

ハードウェアを使わない部分のテスト（CPython）:

```
python tests/test_host.py
```

## 参考資料

- MAX-M10M-00B Data sheet (UBX-22028884)
- MAX-M10M-00B Integration manual (UBX-22038241)
- u-blox M10 SPG 5.10 Interface description (UBX-21035062)

## ライセンス

MIT License(`LICENSE` を参照)。
