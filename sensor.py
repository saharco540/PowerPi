#!/usr/bin/env python
import pandas as pd
from datetime import datetime as dt
from ina219 import INA219
from ina219 import DeviceRangeError
import logging

import pigpio
pi = pigpio.pi()


SHUNT_OHMS = 0.1


def init_sensor(gain):
    print(f"Initializing sensor with gain {gain}")
    ina = INA219(SHUNT_OHMS, log_level=logging.INFO)
    ina.configure(gain=gain, shunt_adc=ina.ADC_12BIT)
    return ina

def get_data_logger(data_lst, max_time_s, interval_ms, save_to_file, save_to_file_on_the_fly=False, set_voltage=0, set_gain=-1):
    try:
        ina = init_sensor(gain=set_gain)
    except Exception as e:
        print(e)
        print("Could not initialize sensor")
    try:
        from csv import writer
        interval_s = interval_ms/1000
        dct = {}
        # if "current" and "voltage" in data_lst,
        if "current" in data_lst and "voltage" in data_lst:
            print("Doing both current and voltage")
            if save_to_file != "":
                pd.DataFrame(columns=['ts', 'current', 'voltage']).to_csv(
                    save_to_file, index=False)
            initial = dt.now().timestamp()
            current_ts = initial
            last_ts = current_ts
            if save_to_file_on_the_fly:
                f = open(save_to_file, 'a', newline='')
                writer = writer(f)
                while current_ts-initial < max_time_s:
                    try:
                        current_ts = dt.now().timestamp()
                        if current_ts-last_ts > interval_s:
                            dct.update({
                                current_ts: dict(
                                    current=ina.current(), voltage=ina.voltage(), shunt_voltage=ina.shunt_voltage())
                            })
                            last_ts = current_ts
                            writer.writerow(
                                [current_ts, dct[current_ts]['current'], dct[current_ts]['voltage']])
                            f.flush()
                            # print(dct[current_ts])
                    except Exception as e:
                        print(e)
                f.close()
            else:
                while current_ts-initial < max_time_s:
                    try:
                        current_ts = dt.now().timestamp()
                        if current_ts-last_ts > interval_s:
                            dct.update({
                                current_ts: dict(
                                    current=ina.current(), voltage=ina.voltage())
                            })
                            last_ts = current_ts
                    except Exception as e:
                        print(e)
            print(f"Done time mode after {current_ts-initial}")
            df = pd.DataFrame.from_dict(
                dct, orient='index').reset_index().rename(columns={'index': 'ts'})
            print(df.head(2))
            if save_to_file:
                df.to_csv(save_to_file, index=False)
            return df
    except Exception as e:
        print("Error in get_data_logger:", e)
        return pd.DataFrame()


def get_sensor_data(ina, start, data_lst):
    if "current" in data_lst and "voltage" in data_lst:
        df = pd.DataFrame(
            dict(current=ina.current(), voltage=ina.voltage()), index=[(pi.get_current_tick()-start)/1000]
        )
        return df
    elif "current" in data_lst:
        df = pd.DataFrame(
            dict(current=ina.current()), index=[(pi.get_current_tick()-start)/1000]
        )
        return df


def get_data_by_count(data_lst=['current', 'voltage'], set_voltage=0, max_time=2, interval_ms=1):
    dct = {}
    initial = pi.get_current_tick()
    if "current" in data_lst and "voltage" in data_lst:
        print("Doing both current and voltage")
        for i in range(1, int((max_time*1000)/0.5)):
            dct.update({
                pi.get_current_tick(): dict(current=ina.current(), voltage=ina.voltage())
            })

    elif "voltage" not in data_lst:
        print("Doing only current")
        initial = pi.get_current_tick()
        print("Doing both current and voltage")
        for i in range(1, int((max_time*1000)/0.5)):
            dct.update({
                pi.get_current_tick(): dict(current=ina.current())
            })
    elif "current" not in data_lst:
        print("Doing only voltage")
        initial = pi.get_current_tick()
        for i in range(1, int((max_time*1000)/0.5)):
            dct.update({
                pi.get_current_tick(): dict(voltage=ina.voltage())
            })
    df = pd.DataFrame.from_dict(
        dct, orient='index').reset_index().rename(columns={'index': 'uS'})
    print(df.head(2))
    df['mS'] = (df['uS']-initial)/1000
    df['mS_diff'] = df['mS'].diff()
    if "voltage" not in data_lst:
        # print(data_lst)
        df['voltage'] = set_voltage
    if "current" not in data_lst:
        df['current'] = 0
    df['wattage'] = df['current']*df['voltage']
    df['mW/h'] = df['wattage']*(df['mS_diff']/1000/3600)
    df['mW/h_cumsum'] = df['mW/h'].cumsum()
    return df
