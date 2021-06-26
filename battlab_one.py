#!/usr/local/bin/python3

import serial
import collections

Transaction = collections.namedtuple(
    'Transaction', 'cmd,response_size,postprocess', defaults=[0, bytes.hex])

transactions = {
    'set_voltage_1v2':  Transaction(cmd=b'a'),
    'set_voltage_1v5':  Transaction(cmd=b'b'),
    'set_voltage_2v4':  Transaction(cmd=b'c'),
    'set_voltage_3v0':  Transaction(cmd=b'd'),
    'set_voltage_3v2':  Transaction(cmd=b'o'),
    'set_voltage_3v6':  Transaction(cmd=b'n'),
    'set_voltage_3v7':  Transaction(cmd=b'e'),
    'set_voltage_4v2':  Transaction(cmd=b'f'),
    'set_voltage_4v5':  Transaction(cmd=b'g'),

    'set_psu_on':       Transaction(cmd=b'h'),
    'set_psu_off':      Transaction(cmd=b'i'),

    'get_calibration':  Transaction(cmd=b'j', response_size=34),
    'get_config':       Transaction(cmd=b'm', response_size=4),
    'get_version':      Transaction(cmd=b'p', response_size=2, postprocess=lambda b: int.from_bytes(b, 'big')/1000),

    'set_current_low':  Transaction(cmd=b'k'),
    'set_current_high': Transaction(cmd=b'l'),

    'set_averages_1':   Transaction(cmd=b's'),  # only in version > 1001
    'set_averages_4':   Transaction(cmd=b't'),
    'set_averages_16':  Transaction(cmd=b'u'),
    'set_averages_64':  Transaction(cmd=b'v'),

    'reboot':           Transaction(cmd=b'w'),  # only in version > 1002

    'set_sample_trig':  Transaction(cmd=b'x'),
    'set_sample_off':   Transaction(cmd=b'y'),
    'set_sample_on':    Transaction(cmd=b'z'),
}


class BattLabOne:

    def __init__(self, device=None):
        self.sp = None
        if device:
            self.connect(device)

    def connect(self, device):
        self.sp = serial.Serial(
            device, baudrate=115200, parity='N', bytesize=8, stopbits=1)
        self.sp.flushInput()
        self.sp.flushOutput()
        return self

    def _do_transaction(self, command):
        transaction = transactions[command]
        self.sp.write(transaction.cmd)
        response = self.sp.read(transaction.response_size)
        return transaction.postprocess(response)


if __name__ == '__main__':
    import sys
    import serial.tools.list_ports

    all_ports = serial.tools.list_ports.comports()
    battlab_one_ports = [p for p in all_ports if p.vid == 0x0403 and p.pid == 0x6001 and p.serial_number[:2] == "BB"]
    if len(battlab_one_ports) == 0:
        print('EE: no BattLab One found', file=sys.stderr)
        raise RuntimeError('no device found')
    elif len(battlab_one_ports) > 1:
        print('EE: multiple BattLab Ones (BattLabs One?) found:', file=sys.stderr)
        raise RuntimeError('too many devices found')
    device = battlab_one_ports[0].device
    print(f'II: found BattLab One at {device}')
    b = BattLabOne(device)
    print('II: firmware version {}'.format(b._do_transaction('get_version')))
    print('II: calibration data {}'.format(b._do_transaction('get_calibration')))
    print('II: config data {}'.format(b._do_transaction('get_config')))
