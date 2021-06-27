#!/usr/local/bin/python3

import serial
import struct
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

    'get_calibration':  Transaction(cmd=b'j', response_size=34, postprocess=lambda b: b),
    'get_config':       Transaction(cmd=b'm', response_size=4),
    'get_version':      Transaction(cmd=b'p', response_size=2, postprocess=lambda b: int.from_bytes(b, 'big')/1000),

    'set_current_low':  Transaction(cmd=b'k'),
    'set_current_high': Transaction(cmd=b'l'),

    'set_averages_1':   Transaction(cmd=b's'),  # only in version > 1001
    'set_averages_4':   Transaction(cmd=b't'),
    'set_averages_16':  Transaction(cmd=b'u'),
    'set_averages_64':  Transaction(cmd=b'v'),

    'reset':            Transaction(cmd=b'w', postprocess=lambda b: time.sleep(1)),  # only in version > 1002

    'set_sample_trig':  Transaction(cmd=b'x'),
    'set_sample_off':   Transaction(cmd=b'y'),
    'set_sample_on':    Transaction(cmd=b'z'),
}

# indexes into the returned calibration data for sense resistor scaling values
cal_indexes = {
    'set_voltage_1v2': 0,
    'set_voltage_1v5': 1,
    'set_voltage_2v4': 2,
    'set_voltage_3v0': 3,
    'set_voltage_3v2': 3,
    'set_voltage_3v6': 4,
    'set_voltage_3v7': 5,
    'set_voltage_4v2': 6,
    'set_voltage_4v5': 7,
}

# indexes into the returned calibration data for sleep current offset values
offset_indexes = {
    'set_voltage_1v2': 8,
    'set_voltage_1v5': 9,
    'set_voltage_2v4': 10,
    'set_voltage_3v0': 11,
    'set_voltage_3v2': 12,
    'set_voltage_3v6': 13,
    'set_voltage_3v7': 14,
    'set_voltage_4v2': 15,
    'set_voltage_4v5': 16,
}

class BattLabOne:

    def __init__(self, device=None):
        self.sp = None
        self.calibration_data = None

        self.cal_adj = None
        self.offset = None
        self.low_current = None

        if device:
            self.connect(device)

    def connect(self, device):
        self.sp = serial.Serial(
            device, baudrate=115200, parity='N', bytesize=8, stopbits=1)
        self.sp.reset_input_buffer()
        self.sp.reset_output_buffer()
        self.calibrate()
        return self

    def calibrate(self):
        calibration_data_raw = self._do_transaction('get_calibration')
        self.calibration_data = struct.unpack('>17H', calibration_data_raw)

    def _do_transaction(self, command):
        transaction = transactions[command]
        self.sp.write(transaction.cmd)
        response = self.sp.read(transaction.response_size)

        # give the firmware time to do whatever, since we can't know when it's completed
        if transaction.response_size == 0:
            time.sleep(0.01)

        # update calibration and offset if we've just set the supply voltage
        if command.startswith('set_voltage_'):
            self.cal_adj = self.calibration_data[cal_indexes[command]]/1000
            self.offset = self.calibration_data[offset_indexes[command]]

        # remember if we've got the low-current sense resistor enabled
        if command.startswith('set_current_'):
            self.low_current = command == 'set_current_low'

        return transaction.postprocess(response)

    def get_sample(self):
        raw_sample = self.sp.read(2)
        sample = int.from_bytes(raw_sample, 'big')
        sense_resistor_scale = 99 if self.low_current else self.cal_adj
        lsb = 0.0025 # magic value?
        current_mA = sample * lsb / sense_resistor_scale #- self.offset
        return current_mA


if __name__ == '__main__':
    import sys
    import time
    import serial.tools.list_ports

    all_ports = serial.tools.list_ports.comports()
    battlab_one_ports = [p for p in all_ports if p.vid == 0x0403 and p.pid == 0x6001 and p.serial_number[:2] == "BB"]
    if len(battlab_one_ports) == 0:
        print('EE: no BattLab One found', file=sys.stderr)
        raise RuntimeError('no device found')
    elif len(battlab_one_ports) > 1:
        print('EE: multiple BattLab Ones (BattLabs One?) found', file=sys.stderr)
        raise RuntimeError('too many devices found')
    device = battlab_one_ports[0].device
    print(f'II: found BattLab One at {device}')
    b = BattLabOne(device)
    print('II: resetting')
    b._do_transaction('reset')
    print('II: firmware version {}'.format(b._do_transaction('get_version')))

    cmds = 'set_voltage_1v2 set_current_high set_averages_64 set_psu_on'.split(' ')
    for cmd in cmds:
        print(f'II: sending command {cmd}')
        b._do_transaction(cmd)
    time.sleep(10)
    print(f'II: starting sampling')
    b._do_transaction('set_sample_on')

    sample_count = 10000
    sample_sum = 0
    sample_min = sys.float_info.max
    sample_max = 0
    start_time = time.time()
    for n in range(sample_count):
        current_mA = b.get_sample()
        print(current_mA, file=f)
        sample_sum += current_mA
        sample_min = min(sample_min, current_mA)
        sample_max = max(sample_max, current_mA)
    end_time = time.time()
    b._do_transaction('set_sample_off')
    b.sp.reset_input_buffer()

    print(f'II: got {sample_count} samples in {end_time-start_time}s')
    print(f'II: cal_adj:{b.cal_adj}')
    print(f'II: min: {sample_min} max: {sample_max} avg: {sample_sum/sample_count}')
