# asyncio example: NMEA goes to the application, AssistNow status comes as periodic UBX output
# (no polling, so no NMEA is interrupted)
import asyncio
from maxm10 import MaxM10, signals, LAYER_RAM

def on_nmea(line):
    if line[3:6] == b'RMC':
        print(line.decode().strip())

async def report(gnss):
    while True:
        await asyncio.sleep(10)
        print('aop', gnss.aop, 'sat', gnss.sat)

async def main():
    gnss = MaxM10(uart_id=0, tx=0, rx=1, resetn=6, pps=22, on_nmea=on_nmea, log=print)
    gnss.begin(115200)
    gnss.apply(signals(gps=True, gal=True, glo=True, qzss=True, sbas=True))
    # Periodic UBX output every 10 navigation epochs, in RAM only (not kept after power-off)
    gnss.apply([('CFG-MSGOUT-UBX_NAV_AOPSTATUS_UART1', 10),
                ('CFG-MSGOUT-UBX_NAV_SAT_UART1', 10)], layers=LAYER_RAM)
    asyncio.create_task(gnss.run())
    await report(gnss)

asyncio.run(main())
