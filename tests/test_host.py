# Host (CPython) tests for the parts without hardware: python tests/test_host.py
import os, struct, sys, types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.modules.setdefault('machine', types.SimpleNamespace(Pin=None, UART=None)) # stub for import

from maxm10 import ubx, signals, sbas_prnscanmask, SBAS_PRN_MSAS
from maxm10.keys import key_id, key_name, is_signal_key

def nmea(body):
    cs = 0
    for b in body.encode():
        cs ^= b
    return ('$%s*%02X\r\n' % (body, cs)).encode()

def collect(chunks, **kw):
    out = []
    sp = ubx.Splitter(lambda l: out.append(('nmea', l)),
                      lambda c, i, p: out.append(('ubx', c, i, p)), **kw)
    for c in chunks:
        sp.feed(c)
    return out, sp

def test_frame():
    # MON-VER poll from the u-blox documentation
    assert ubx.frame(0x0A, 0x04) == bytes.fromhex('b5620a0400000e34')

def test_split_mixed_and_chunked():
    gga = nmea('GNGGA,123519.00,,,,,0,00,99.99,,,,,,')
    ack = ubx.frame(0x05, 0x01, b'\x06\x8a')
    stream = b'\x00\xff' + gga + ack + gga
    for size in (1, 3, 7, len(stream)):
        chunks = [stream[i:i + size] for i in range(0, len(stream), size)]
        out, sp = collect(chunks)
        assert out == [('nmea', gga), ('ubx', 5, 1, b'\x06\x8a'), ('nmea', gga)], (size, out)
        assert sp.dropped == 2

def test_split_recovers_after_garbage():
    ack = ubx.frame(0x05, 0x01, b'\x06\x8a')
    rmc = nmea('GNRMC,,V,,,,,,,,,,N,V')
    out, sp = collect([b'$GN' + ack + rmc]) # '$' garbage without newline before UBX
    assert out == [('ubx', 5, 1, b'\x06\x8a'), ('nmea', rmc)], out
    bad = bytearray(ack)
    bad[-1] ^= 0xFF
    out, sp = collect([bytes(bad) + rmc])
    assert out == [('nmea', rmc)] and sp.ubx_errors == 1
    out, sp = collect([rmc.replace(b'*', b'*0')]) # wrong checksum
    assert out == [] and sp.nmea_errors == 1

def test_valget_roundtrip():
    items = [(key_id('CFG-UART1-BAUDRATE'), 115200), (key_id('CFG-NAVSPG-DYNMODEL'), 4),
             (key_id('CFG-SBAS-PRNSCANMASK'), 0x20200), (key_id('CFG-ANA-USE_ANA'), 1)]
    p = ubx.valset_payload(items, ubx.LAYER_RAM)
    p = struct.pack('<BBH', 1, 0, 0) + p[4:] # VALGET response has the same layout
    assert ubx.parse_valget(p) == dict(items)

def test_decoders():
    p = struct.pack('<IBB10x', 0, 1, 0)
    assert ubx.decode_aopstatus(p) == (True, False)
    st = ubx.decode_nav_status(struct.pack('<IBBBBII', 0, 3, 0x03, 0, 0, 3400, 61000))
    assert st['gps_fix'] == 3 and st['fix_ok'] and st['diff_soln'] and st['ttff_ms'] == 3400
    sv = lambda cno, flags: struct.pack('<BBBbhhI', 0, 1, cno, 45, 90, 0, flags)
    p = struct.pack('<IBB2x', 0, 1, 2) + sv(40, (1 << 3) | (4 << 8) | (1 << 14)) + sv(0, 1 << 11)
    c = ubx.decode_nav_sat(p)
    assert (c['tracked'], c['used'], c['aop'], c['aop_used'], c['eph']) == (1, 1, 1, 1, 1), c

def test_config_helpers():
    s = dict(signals(gps=True, gal=True, glo=True, qzss=True, qzss_l1s=True, sbas=True))
    assert s['CFG-SIGNAL-GLO_ENA'] == 1 and s['CFG-SIGNAL-BDS_ENA'] == 0
    assert s['CFG-SIGNAL-QZSS_L1S_ENA'] == 1 and len(s) == 14
    for bad in (dict(glo=True, bds_b1i=True), dict(gps=False), dict(qzss=False, qzss_l1s=True)):
        try:
            signals(**bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)
    assert sbas_prnscanmask(SBAS_PRN_MSAS) == 0x20200
    assert is_signal_key('CFG-SIGNAL-GPS_ENA') and not is_signal_key('CFG-ANA-USE_ANA')
    assert key_name(0x10230001) == 'CFG-ANA-USE_ANA' and key_name(0x12345678) == '0x12345678'

if __name__ == '__main__':
    for name, f in sorted(globals().items()):
        if name.startswith('test_'):
            f()
            print('ok', name)
